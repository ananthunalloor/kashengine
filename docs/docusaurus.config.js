const config = {
  title: 'Kash Engine Developer Docs',
  tagline: 'Architecture, application behavior, function reference, and operations',
  url: process.env.DOCS_URL || 'https://localhost',
  baseUrl: '/docs/',
  trailingSlash: true,
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      },
    ],
  ],
  themeConfig: {
    navbar: {
      title: 'Kash Engine',
      items: [
        {to: '/getting-started', label: 'Developer guide', position: 'left'},
        {to: '/reference/generated/', label: 'Python API', position: 'left'},
        {
          href: 'https://github.com/ananthunalloor/kashengine',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Project',
          items: [
            {label: 'Repository', href: 'https://github.com/ananthunalloor/kashengine'},
          ],
        },
        {
          title: 'Documentation',
          items: [
            {label: 'Getting started', to: '/getting-started'},
            {label: 'Architecture', to: '/architecture/overview'},
            {label: 'Function reference', to: '/reference/generated/'},
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Kash Engine contributors.`,
    },
    prism: {
      theme: require('prism-react-renderer').themes.github,
      darkTheme: require('prism-react-renderer').themes.dracula,
    },
  },
};

module.exports = config;
