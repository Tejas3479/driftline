/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // vega-canvas tries to require('canvas') for Node.js SSR rendering.
    // We only render Vega client-side, so safely ignore this module.
    config.resolve.fallback = {
      ...config.resolve.fallback,
      canvas: false,
    };
    return config;
  },
};

module.exports = nextConfig;
