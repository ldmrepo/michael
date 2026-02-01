/** @type {import('next').NextConfig} */
const nextConfig = {
    rewrites: async () => {
        return [
            {
                // Proxy API requests to Michael backend
                source: '/api/:path*',
                destination: 'http://127.0.0.1:3000/api/:path*',
            },
        ]
    },
};

module.exports = nextConfig;
