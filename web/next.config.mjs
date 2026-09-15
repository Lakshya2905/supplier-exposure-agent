/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  sassOptions: {
    // Carbon's stylesheets `@use` each other by bare package path.
    includePaths: ['./node_modules'],
    // Carbon v11 still emits `@import`-era deprecations through Dart Sass.
    // Silenced rather than patched: they come from inside the dependency and
    // there is nothing in this repository to fix.
    silenceDeprecations: ['mixed-decls', 'global-builtin', 'import',
                          'legacy-js-api', 'slash-div', 'color-functions'],
    quietDeps: true,
  },
  transpilePackages: ['@carbon/charts', '@carbon/charts-react'],
};

export default nextConfig;
