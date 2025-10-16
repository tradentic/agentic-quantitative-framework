import {join} from 'path';
import type {Config} from '@docusaurus/types';
import type {ThemeConfig} from '@docusaurus/preset-classic';
import {themes as prismThemes} from 'prism-react-renderer';

const themeConfig: ThemeConfig = {
  navbar: {
    title: 'Starter Docs',
    logo: {
      alt: 'Next.js + Supabase Starter logo',
      src: 'img/logo.svg',
    },
    items: [
      {
        type: 'doc',
        docId: 'intro',
        position: 'left',
        label: 'Intro',
      },
      {
        href: 'https://github.com/airnub/next-supabase-i18n-a11y-starter',
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
            label: 'Getting Started',
            to: '/',
          },
        ],
      },
      {
        title: 'Community',
        items: [
          {
            label: 'GitHub Discussions',
            href: 'https://github.com/airnub/next-supabase-i18n-a11y-starter/discussions',
          },
          {
            label: 'Issues',
            href: 'https://github.com/airnub/next-supabase-i18n-a11y-starter/issues',
          },
        ],
      },
    ],
    copyright: `© ${new Date().getFullYear()} Next.js + Supabase Starter`,
  },
  prism: {
    theme: prismThemes.github,
    darkTheme: prismThemes.dracula,
  },
};

const config: Config = {
  title: 'Next.js + Supabase Starter Docs',
  tagline: 'Documentation for the Next.js, Supabase, i18n, and a11y starter kit',
  favicon: 'img/logo.svg',
  url: 'https://airnub.github.io',
  baseUrl: '/next-supabase-i18n-a11y-starter/',
  organizationName: 'airnub',
  projectName: 'next-supabase-i18n-a11y-starter',
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
          editUrl:
            'https://github.com/airnub/next-supabase-i18n-a11y-starter/tree/main/docs/',
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
