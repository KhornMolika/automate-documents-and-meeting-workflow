import { defineConfig } from 'wxt';
import vue from '@vitejs/plugin-vue';

// See https://wxt.dev/api/config.html
export default defineConfig({
  outDir: 'dist',
  vite: () => ({
    plugins: [vue()],
  }),
  manifest: {
    name: 'AUB Meeting Assistant — Google Meet Audio Ingress',
    description: 'Captures Google Meet tab audio and the microphone for localized Khmer-English transcription and AI minutes.',
    version: '1.2.2',
    minimum_chrome_version: '116',
    icons: {
      16: 'icon-16.png',
      32: 'icon-32.png',
      48: 'icon-48.png',
      128: 'icon-128.png',
    },
    permissions: [
      'tabCapture',
      'activeTab',
      'tabs',
      'storage',
      'offscreen'
    ],
    host_permissions: [
      'https://meet.google.com/*',
      'http://localhost:8000/*',
      'http://127.0.0.1:8000/*'
    ],
    action: {
      default_title: 'AUB Meeting Ingress',
      default_popup: 'popup.html',
      default_icon: {
        16: 'icon-16.png',
        32: 'icon-32.png',
        48: 'icon-48.png',
        128: 'icon-128.png',
      },
    }
  }
});
