// Next.js configuration
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    domains: ['proppulse-public.s3.amazonaws.com', 'proppulse-assets.s3.amazonaws.com'],
  },
  i18n: {
    locales: ['en'],
    defaultLocale: 'en',
  },
  env: {
    NEXT_PUBLIC_MAGIC_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_MAGIC_PUBLISHABLE_KEY,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_ENABLE_GOOGLE_OAUTH: process.env.NEXT_PUBLIC_ENABLE_GOOGLE_OAUTH || 'false',
    NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY,
  },
};

module.exports = nextConfig;
