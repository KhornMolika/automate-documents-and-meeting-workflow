export default defineBackground(() => {
  console.log('[AUB Ingress Extension] Service worker initialized.');

  let activeStream: MediaStream | null = null;
  let socket: WebSocket | null = null;

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'START_CAPTURE') {
      const meetingId = message.meetingId || 'demo-meeting-01';
      const wsUrl = message.wsUrl || `ws://localhost:8000/ws/audio/${meetingId}`;

      console.log(`[AUB Ingress] Starting capture for meeting ${meetingId} -> ${wsUrl}`);

      // Initialize WebSocket connection
      try {
        socket = new WebSocket(wsUrl);
        socket.binaryType = 'arraybuffer';

        socket.onopen = () => {
          console.log('[AUB Ingress] WebSocket connected to backend gateway.');
          sendResponse({ status: 'CONNECTED', meetingId });
        };

        socket.onerror = (err) => {
          console.error('[AUB Ingress] WebSocket error:', err);
        };
      } catch (err) {
        sendResponse({ status: 'ERROR', error: String(err) });
      }

      return true; // async sendResponse
    }

    if (message.action === 'STOP_CAPTURE') {
      if (socket) {
        socket.close();
        socket = null;
      }
      if (activeStream) {
        activeStream.getTracks().forEach((track) => track.stop());
        activeStream = null;
      }
      sendResponse({ status: 'STOPPED' });
      return true;
    }

    if (message.action === 'GET_STATUS') {
      sendResponse({
        isCapturing: socket !== null && socket.readyState === WebSocket.OPEN,
      });
      return true;
    }
  });
});
