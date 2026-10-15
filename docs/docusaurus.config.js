// @ts-check
// Docusaurus configuration for the Kash Engine developer documentation.
// The site is served under /docs/ by the "docs" service. Caddy sends /docs to it.

const {themes} = require('prism-react-renderer');

const REPO = 'https://github.com/ananthunalloor/kashengine';

const SITE_URL = process.env.DOCS_URL || 'https://localhost';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Kash Engine Developer Docs',
  tagline: 'Architecture, HTTP API, operations, and the reference of every function',
  url: SITE_URL,
  baseUrl: '/docs/',
  trailingSlash: true,
  // The documentation is for developers of this project. Search engines must not index it.
  noIndex: true,
  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  onDuplicateRoutes: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },
  i18n: {defaultLocale: 'en', locales: ['en']},
  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
          // Generated pages (reference/generated) are not edited by hand. They have no edit link.
          editUrl: ({docPath}) =>
            docPath.startsWith('reference/generated/')
              ? undefined
              : `${REPO}/edit/main/docs/docs/${docPath}`,
        },
        blog: false,
        theme: {customCss: require.resolve('./src/css/custom.css')},
      },
    ],
  ],
  themes: [
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      /** @type {import('@easyops-cn/docusaurus-search-local').PluginOptions} */
      ({
        hashed: true,
        indexBlog: false,
        docsRouteBasePath: '/',
        highlightSearchTermsOnTargetPage: true,
        explicitSearchResultPath: true,
      }),
    ],
  ],
  themeConfig: {
    colorMode: {respectPrefersColorScheme: true},
    navbar: {
      title: 'Kash Engine',
      items: [
        {type: 'docSidebar', sidebarId: 'developerSidebar', label: 'Guides', position: 'left'},
        {to: '/api/overview', label: 'HTTP API', position: 'left', activeBaseRegex: '/api/'},
        {
          to: '/reference/generated/http/',
          label: 'API reference',
          position: 'left',
          activeBaseRegex: '/reference/generated/http',
        },
        {
          to: '/reference/generated/python/',
          label: 'Python reference',
          position: 'left',
          activeBaseRegex: '/reference/generated/(python|system)',
        },
        // The Swagger UI belongs to the app, not to this site. It is outside the /docs/ base path.
        {href: `${SITE_URL}/api/v1/docs`, label: 'Swagger UI', position: 'right'},
        {href: REPO, label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Guides',
          items: [
            {label: 'Getting started', to: '/getting-started'},
            {label: 'Architecture', to: '/architecture/overview'},
            {label: 'Operations', to: '/operations/self-hosting'},
          ],
        },
        {
          title: 'Reference',
          items: [
            {label: 'HTTP API', to: '/api/overview'},
            {label: 'Python reference', to: '/reference/generated/python/'},
            {label: 'Settings', to: '/reference/generated/system/settings'},
          ],
        },
        {title: 'Project', items: [{label: 'Repository', href: REPO}]},
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Kash Engine contributors.`,
    },
    prism: {
      theme: themes.github,
      darkTheme: themes.dracula,
      additionalLanguages: ['bash', 'json', 'python', 'nginx', 'docker', 'yaml', 'ini'],
    },
  },
};

module.exports = config;
