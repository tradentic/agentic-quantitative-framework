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
      {type: 'doc', docId: 'intro', position: 'left', label: 'Intro'},
      {type: 'doc', docId: 'architecture/quant_ai_strategy_design', position: 'left', label: 'Architecture'},
      {type: 'doc', docId: 'agents', position: 'left', label: 'Agents'},
      {
        href: 'https://github.com/airnub/agentic-quantitative-framework',
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
          {label: 'Welcome', to: '/'},
          {label: 'Architecture', to: '/architecture/quant_ai_strategy_design'},
        ],
      },
      {
        title: 'Community',
        items: [
          {
            label: 'GitHub Discussions',
            href: 'https://github.com/airnub/agentic-quantitative-framework/discussions',
          },
          {
            label: 'Issues',
            href: 'https://github.com/airnub/agentic-quantitative-framework/issues',
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
  tagline: 'LangGraph-native, Supabase-first workflow for quantitative signal discovery',
  favicon: 'img/logo.svg',
  url: 'https://agentic-quantitative-framework.dev',
  baseUrl: '/',
  organizationName: 'airnub',
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
          editUrl: 'https://github.com/airnub/agentic-quantitative-framework/tree/main/docs/',
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
