import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'FluentInstall 流畅入库',
  description: '免费开源的 Steam 入库工具，基于 cai-install 后端改编，采用 Fluent Design 设计',

  base: '/Fluent-Install/',

  head: [
    ['link', { rel: 'icon', href: '/icon.ico' }],
    ['link', { rel: 'shortcut icon', href: '/icon.ico' }]
  ],

  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      themeConfig: {
        nav: [
          { text: '首页', link: '/' },
          {
            text: '入门指南',
            items: [
              { text: '安装前准备', link: '/guide/prepare' },
              { text: '安装 FluentInstall', link: '/guide/install' },
              { text: '使用程序', link: '/guide/usage' },
              { text: '界面截图', link: '/guide/screenshots' },
              { text: '视频宣传', link: '/guide/videos' }
            ]
          },
          { text: '常见问题', link: '/faq/' },
          {
            text: '关于',
            items: [
              { text: '关于项目', link: '/about' },
              { text: '鸣谢', link: '/thanks' },
              { text: '捐赠', link: '/donate' }
            ]
          },
          {
            text: '社区与交流',
            items: [
              { text: 'GitHub Issue', link: 'https://github.com/zhouchentao666/Fluent-Install/issues' },
              { text: 'QQ频道', link: 'https://pd.qq.com/s/fg1vd0v17' },
              { text: 'Q群', link: 'https://qm.qq.com/q/gtTLap5Jw4' },
              { text: 'TG群', link: 'https://t.me/+vTrqXKpRJE9kNmVl' }
            ]
          }
        ],
        sidebar: [
          {
            text: '入门指南',
            items: [
              { text: '安装前准备', link: '/guide/prepare' },
              { text: '安装 FluentInstall', link: '/guide/install' },
              { text: '使用程序', link: '/guide/usage' },
              { text: '界面截图', link: '/guide/screenshots' },
              { text: '视频宣传', link: '/guide/videos' }
            ]
          },
          {
            text: '常见问题',
            items: [
              { text: 'FAQ', link: '/faq/' }
            ]
          },
          {
            text: '关于',
            items: [
              { text: '关于项目', link: '/about' },
              { text: '鸣谢', link: '/thanks' },
              { text: '捐赠', link: '/donate' }
            ]
          }
        ],
        footer: {
          message: 'FluentInstall 流畅入库 - 免费开源的 Steam 入库工具',
          copyright: 'Copyright © 2024-present'
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/zhouchentao666/Fluent-Install' }
        ]
      }
    },
    'zh-tw': {
      label: '繁體中文',
      lang: 'zh-TW',
      themeConfig: {
        nav: [
          { text: '首頁', link: '/zh-tw/' },
          {
            text: '入門指南',
            items: [
              { text: '安裝前準備', link: '/zh-tw/guide/prepare' },
              { text: '安裝 FluentInstall', link: '/zh-tw/guide/install' },
              { text: '使用程式', link: '/zh-tw/guide/usage' },
              { text: '介面截圖', link: '/zh-tw/guide/screenshots' },
              { text: '影片宣傳', link: '/zh-tw/guide/videos' }
            ]
          },
          { text: '常見問題', link: '/zh-tw/faq/' },
          {
            text: '關於',
            items: [
              { text: '關於專案', link: '/zh-tw/about' },
              { text: '鳴謝', link: '/zh-tw/thanks' },
              { text: '捐贈', link: '/zh-tw/donate' }
            ]
          },
          {
            text: '社群與交流',
            items: [
              { text: 'GitHub Issue', link: 'https://github.com/zhouchentao666/Fluent-Install/issues' },
              { text: 'QQ頻道', link: 'https://pd.qq.com/s/fg1vd0v17' },
              { text: 'QQ群', link: 'https://qm.qq.com/q/gtTLap5Jw4' },
              { text: 'TG群', link: 'https://t.me/+vTrqXKpRJE9kNmVl' }
            ]
          }
        ],
        sidebar: [
          {
            text: '入門指南',
            items: [
              { text: '安裝前準備', link: '/zh-tw/guide/prepare' },
              { text: '安裝 FluentInstall', link: '/zh-tw/guide/install' },
              { text: '使用程式', link: '/zh-tw/guide/usage' },
              { text: '介面截圖', link: '/zh-tw/guide/screenshots' },
              { text: '影片宣傳', link: '/zh-tw/guide/videos' }
            ]
          },
          {
            text: '常見問題',
            items: [
              { text: 'FAQ', link: '/zh-tw/faq/' }
            ]
          },
          {
            text: '關於',
            items: [
              { text: '關於專案', link: '/zh-tw/about' },
              { text: '鳴謝', link: '/zh-tw/thanks' },
              { text: '捐贈', link: '/zh-tw/donate' }
            ]
          }
        ],
        footer: {
          message: 'FluentInstall 流暢入庫 - 免費開源的 Steam 入庫工具',
          copyright: 'Copyright © 2024-present'
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/zhouchentao666/Fluent-Install' }
        ]
      }
    },
    'en': {
      label: 'English',
      lang: 'en-US',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/en/' },
          {
            text: 'Quick Start',
            items: [
              { text: 'Preparation', link: '/en/guide/prepare' },
              { text: 'Installation', link: '/en/guide/install' },
              { text: 'Usage', link: '/en/guide/usage' },
              { text: 'Screenshots', link: '/en/guide/screenshots' },
              { text: 'Videos', link: '/en/guide/videos' }
            ]
          },
          { text: 'FAQ', link: '/en/faq/' },
          {
            text: 'About',
            items: [
              { text: 'About Project', link: '/en/about' },
              { text: 'Credits', link: '/en/thanks' },
              { text: 'Donate', link: '/en/donate' }
            ]
          },
          {
            text: 'Community',
            items: [
              { text: 'GitHub Issue', link: 'https://github.com/zhouchentao666/Fluent-Install/issues' },
              { text: 'QQ Channel', link: 'https://pd.qq.com/s/fg1vd0v17' },
              { text: 'QQ Group', link: 'https://qm.qq.com/q/gtTLap5Jw4' },
              { text: 'Telegram', link: 'https://t.me/+vTrqXKpRJE9kNmVl' }
            ]
          }
        ],
        sidebar: [
          {
            text: 'Quick Start',
            items: [
              { text: 'Preparation', link: '/en/guide/prepare' },
              { text: 'Installation', link: '/en/guide/install' },
              { text: 'Usage', link: '/en/guide/usage' },
              { text: 'Screenshots', link: '/en/guide/screenshots' },
              { text: 'Videos', link: '/en/guide/videos' }
            ]
          },
          {
            text: 'FAQ',
            items: [
              { text: 'FAQ', link: '/en/faq/' }
            ]
          },
          {
            text: 'About',
            items: [
              { text: 'About Project', link: '/en/about' },
              { text: 'Credits', link: '/en/thanks' },
              { text: 'Donate', link: '/en/donate' }
            ]
          }
        ],
        footer: {
          message: 'FluentInstall - Free & Open Source Steam Library Tool',
          copyright: 'Copyright © 2024-present'
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/zhouchentao666/Fluent-Install' }
        ]
      }
    }
  },

  themeConfig: {
    logo: '/icon.ico',
    search: {
      provider: 'local'
    }
  }
})
