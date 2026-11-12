/* Layover Logbook settings
   Paste your Supabase details between the quotes (Supabase: Project Settings > API Keys).
   The publishable (or "anon public") key is made to be public, so it is safe in this file.
   Never put the secret / service_role key here. */
window.LAYOVER_CONFIG = {
  supabaseUrl: "https://zzgtxastnmxzffygdkrg.supabase.co",   // e.g. "https://abcdefghijkl.supabase.co"
  supabaseKey: "sb_publishable_zdlCSLo3OOHr7GdWQmCHng_hpQCiYT-",   // e.g. "sb_publishable_..." or the long "anon public" key

  /* Pro subscription (payments by Paddle). Fill these in from your Paddle dashboard.
     All of these values are made to be public, so they are safe in this file.
     Never put a Paddle API key or webhook secret here. */
  pro: {
    monthlyPrice: "$4.99",      // shown on the upgrade screen; keep it the same as the price in Paddle
    yearlyPrice: "$39.99",
    paddleEnv: "production",    // "sandbox" while testing with Paddle's sandbox, then "production"
    paddleToken: "",            // Paddle > Developer tools > Authentication > Client-side token ("live_..." or "test_...")
    paddleMonthlyId: "",        // Paddle > Catalog > your product > monthly price ID ("pri_...")
    paddleYearlyId: "",         // yearly price ID ("pri_...")
    manageUrl: ""               // Paddle > Checkout > Customer portal link, so subscribers can cancel or change card
  }
};
