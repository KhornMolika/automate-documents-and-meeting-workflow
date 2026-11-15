import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  manifest: {
    name: 'AUB Meeting Assistant — Google Meet Audio Ingress',
    description: 'Captures Google Meet tab audio for localized Khmer-English transcription & Google Gemini MoM synthesis.',
    version: '1.0.0',
    permissions: [
      'tabCapture',
      'activeTab',
      'storage',
      'offscreen'
    ],
    host_permissions: [
      'https://meet.google.com/*'
    ],
    action: {
      default_title: 'AUB Meeting Ingress'
    }
  }
});
