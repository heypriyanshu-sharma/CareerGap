const SUPABASE_URL = "https://lbtndermohgljdtlluxp.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_32ZDZ2yRdxDbzrQaEUBstA_4arJ9hb5";

const careerGapSupabase = supabase.createClient(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
);

// Single shared sign-out path for every page, so the account menu,
// Settings and the post-deletion redirect all invalidate the session
// the same way instead of each owning their own auth logic.
//
// Returns { ok: true } once Supabase has cleared the session and the
// redirect to login.html has been requested, or { ok: false, error }
// when Supabase refused so the caller can restore its button and
// surface a message.
async function careerGapSignOut() {
    const { error } = await careerGapSupabase.auth.signOut();

    if (error) {
        return { ok: false, error: error };
    }

    window.location.replace("login.html");

    return { ok: true };
}