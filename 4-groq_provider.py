"""Official Groq client with bounded, secret-safe, single-attempt transport."""
import json
import logging
import os
import time
from types import SimpleNamespace
import httpx
from groq import Groq, APIStatusError, APITimeoutError, APIConnectionError

# SDK debug logs include request bodies. AI evidence must never enter logs.
for _logger_name in ('groq','groq._base_client'):
    logging.getLogger(_logger_name).disabled = True

BASE_URL = 'https://api.groq.com'
ENDPOINT = BASE_URL + '/openai/v1/chat/completions'
MAX_RESPONSE_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 25
MESSAGES = {
    'configuration': 'AI provider configuration is unsupported.',
    'missing_key': 'AI service unavailable: API key not configured.',
    'rate_limit': 'AI free-tier limit reached. Try again later.',
    'access': 'AI provider access is unavailable.',
    'request_failed': 'AI provider request failed.',
    'timeout': 'AI provider request timed out.',
    'network': 'AI provider connection is unavailable.',
    'oversize': 'AI provider response exceeded the size limit.',
    'invalid_completion': 'AI provider returned an incomplete or invalid response.',
    'output_invalid': 'AI output was invalid.',
}

class AIProviderError(RuntimeError):
    def __init__(self, category, http_status=None):
        self.category = category if category in MESSAGES else 'request_failed'
        self.http_status = http_status if isinstance(http_status, int) and 100 <= http_status <= 599 else None
        super().__init__(MESSAGES[self.category])

class BoundedStream(httpx.SyncByteStream):
    def __init__(self, inner, deadline):
        self.inner, self.deadline = inner, deadline
    def __iter__(self):
        total = 0
        for chunk in self.inner:
            if time.monotonic() > self.deadline:
                raise AIProviderError('timeout')
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise AIProviderError('oversize')
            yield chunk
    def close(self):
        self.inner.close()

class GuardedTransport(httpx.BaseTransport):
    def __init__(self, inner=None):
        self.inner = inner if inner is not None else httpx.HTTPTransport(retries=0, trust_env=False)
    def handle_request(self, req):
        if str(req.url) != ENDPOINT or req.method != 'POST':
            raise AIProviderError('request_failed')
        deadline = time.monotonic() + TIMEOUT_SECONDS
        response = self.inner.handle_request(req)
        if response.headers.get("content-encoding", "identity").lower() not in ("", "identity"):
            response.close()
            raise AIProviderError("invalid_completion")
        response.stream = BoundedStream(response.stream, deadline)
        if response.is_stream_consumed:
            if len(response.content) > MAX_RESPONSE_BYTES:
                response.close()
                raise AIProviderError("oversize")
        elif response.status_code >= 300:
            # Bound errors before SDK eagerly reads and wraps status failures.
            try:
                response.read()
            except Exception:
                response.close()
                raise
        return response
    def close(self):
        self.inner.close()

class GroqInteractions:
    def __init__(self, api_key):
        self._api_key = api_key
    def create(self, *, model, input, generation_config=None):
        if not self._api_key:
            raise AIProviderError('missing_key')
        if os.environ.get("GROQ_CUSTOM_HEADERS"):
            raise AIProviderError("configuration")
        config = generation_config or {}
        args = dict(model=model, messages=[{'role':'user','content':input}],
                    temperature=config.get('temperature',0.3),
                    max_completion_tokens=config.get('max_output_tokens',4096),
                    reasoning_effort='low')
        if generation_config is not None:
            args['response_format'] = {'type':'json_object'}
        try:
            with httpx.Client(transport=GuardedTransport(), timeout=TIMEOUT_SECONDS,
                              follow_redirects=False, trust_env=False, headers={"Accept-Encoding":"identity"}) as http:
                with Groq(api_key=self._api_key, base_url=BASE_URL, max_retries=0,
                          timeout=TIMEOUT_SECONDS, http_client=http) as client:
                    with client.chat.completions.with_streaming_response.create(**args) as response:
                        raw = bytearray()
                        for chunk in response.iter_bytes(chunk_size=65536):
                            raw.extend(chunk)
                            if len(raw) > MAX_RESPONSE_BYTES:
                                raise AIProviderError('oversize')
        except AIProviderError:
            raise
        except APIStatusError as exc:
            category = 'rate_limit' if exc.status_code == 429 else 'access' if exc.status_code in (401,403) else 'request_failed'
            raise AIProviderError(category, exc.status_code) from None
        except APITimeoutError:
            raise AIProviderError('timeout') from None
        except APIConnectionError as exc:
            # SDK wraps transport exceptions. Retain only our fixed categories.
            if isinstance(exc.__cause__, AIProviderError):
                raise AIProviderError(exc.__cause__.category) from None
            raise AIProviderError('network') from None
        except Exception:
            raise AIProviderError('request_failed') from None
        try:
            payload = json.loads(raw)
            choice = payload['choices'][0]
            text = choice['message']['content']
            if choice.get('finish_reason') != 'stop' or not isinstance(text,str) or not text.strip():
                raise ValueError()
        except (ValueError,KeyError,IndexError,TypeError):
            raise AIProviderError('invalid_completion') from None
        return SimpleNamespace(output_text=text.strip())

class GroqClient:
    def __init__(self, api_key):
        self.interactions = GroqInteractions(api_key)
