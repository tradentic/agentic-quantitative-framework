import {join} from 'path';
import type {Config} from '@docusaurus/types';
import type {ThemeConfig} from '@docusaurus/preset-classic';
import {themes as prismThemes} from 'prism-react-renderer';

const themeConfig: ThemeConfig = {
  navbar: {
    title: 'Agentic Quantitative Framework',
    logo: {
      alt: 'Agentic Quantitative Framework logo',
      src: 'img/logo.svg',
    },
    items: [
      {
        type: 'doc',
        docId: 'overview',
        position: 'left',
        label: 'Overview',
      },
      {
        type: 'doc',
        docId: 'agents',
        position: 'left',
        label: 'Agents',
      },
      {
        href: 'https://github.com/agentic-quantitative/agentic-quantitative-framework',
        label: 'GitHub',
        position: 'right',
      },
    ],
  },
  footer: {
    style: 'dark',
    links: [
      {
        title: 'Docs',
        items: [
          {
            label: 'Overview',
            to: '/',
          },
          {
            label: 'Architecture',
            to: '/architecture',
          },
        ],
      },
      {
        title: 'Community',
        items: [
          {
            label: 'GitHub Issues',
            href: 'https://github.com/agentic-quantitative/agentic-quantitative-framework/issues',
          },
        ],
      },
    ],
    copyright: `© ${new Date().getFullYear()} Agentic Quantitative Framework`,
  },
  prism: {
    theme: prismThemes.github,
    darkTheme: prismThemes.dracula,
  },
};

const config: Config = {
  title: 'Agentic Quantitative Framework Docs',
  tagline: 'LangGraph-native research automation for quantitative signals',
  favicon: 'img/logo.svg',
  url: 'https://agentic-quantitative.github.io',
  baseUrl: '/',
  organizationName: 'agentic-quantitative',
  projectName: 'agentic-quantitative-framework',
  onBrokenLinks: 'throw',
  trailingSlash: false,
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
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
          sidebarPath: join(__dirname, 'sidebars.ts'),
          showLastUpdateAuthor: true,
          showLastUpdateTime: true,
        },
        blog: false,
        pages: false,
        theme: {
          customCss: join(__dirname, 'src/css/custom.css'),
        },
      },
    ],
  ],
  themeConfig,
};

export default config;
