const SUPABASE_URL = "https://lbtndermohgljdtlluxp.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_32ZDZ2yRdxDbzrQaEUBstA_4arJ9hb5";

const careerGapSupabase = supabase.createClient(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
);