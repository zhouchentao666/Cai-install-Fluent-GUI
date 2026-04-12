import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Cai Install',
  description: 'Fluent Design 版本的 Steam 游戏解锁工具',

  base: '/Fluent-Install/',

  head: [
    ['link', { rel: 'icon', href: '/Fluent-Install/icon.ico' }]
  ],

  outDir: '../dist',

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '入门指南', link: '/guide/getting-started' },
      { text: '常见问题', link: '/faq/' }
    ],

    sidebar: [
      {
        text: '指南',
        items: [
          { text: '入门指南', link: '/guide/getting-started' }
        ]
      },
      {
        text: '常见问题',
        items: [
          { text: 'FAQ', link: '/faq/' }
        ]
      }
    ],

    footer: {
      message: '基于 PyQt6-Fluent-Widgets 构建',
      copyright: 'Copyright © 2024-present'
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/zhouchentao666/Fluent-Install' }
    ]
  }
})
