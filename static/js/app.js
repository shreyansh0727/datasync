(() => {
  const usernameInput = document.getElementById('username');
  const roomInput = document.getElementById('room');
  const generateBtn = document.getElementById('generateBtn');
  const connectBtn = document.getElementById('connectBtn');
  const disconnectBtn = document.getElementById('disconnectBtn');
  const sendMsgBtn = document.getElementById('sendMsg');
  const sendFileBtn = document.getElementById('sendFile');
  const msgInput = document.getElementById('msg');
  const fileInput = document.getElementById('file');
  const logEl = document.getElementById('log');
  const downloadsEl = document.getElementById('downloads');
  const sendProgEl = document.getElementById('sendProg');
  const recvProgEl = document.getElementById('recvProg');
  const sendPercentEl = document.getElementById('sendPercent');
  const recvPercentEl = document.getElementById('recvPercent');
  const statusBadge = document.getElementById('statusBadge');
  const qrSection = document.getElementById('qrSection');
  const qrContainer = document.getElementById('qrContainer');
  const toggleQr = document.getElementById('toggleQr');

  let ws = null;
  let qrCode = null;
  const recvState = new Map();

  // Load saved username
  const savedName = localStorage.getItem('datasync_username');
  if (savedName) {
    usernameInput.value = savedName;
  }

  // Save username on change
  usernameInput.addEventListener('change', () => {
    localStorage.setItem('datasync_username', usernameInput.value);
  });

  function log(text) {
    const div = document.createElement('div');
    div.textContent = text;
    logEl.appendChild(div);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function wsUrl(path) {
    const proto = (location.protocol === 'https:') ? 'wss' : 'ws';
    return `${proto}://${location.host}${path}`;
  }

  function setStatus(text, connected = false) {
    statusBadge.textContent = text;
    if (connected) {
      statusBadge.classList.add('connected');
    } else {
      statusBadge.classList.remove('connected');
    }
  }

  function generateRoomId() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let result = '';
    for (let i = 0; i < 6; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }

  generateBtn.onclick = () => {
    roomInput.value = generateRoomId();
  };

  function showQRCode(roomId) {
    const roomUrl = `${location.origin}/?room=${encodeURIComponent(roomId)}`;
    qrContainer.innerHTML = '';
    qrCode = new QRCode(qrContainer, {
      text: roomUrl,
      width: 200,
      height: 200,
      colorDark: '#1a1a1a',
      colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.H
    });
    qrSection.style.display = 'block';
  }

  toggleQr.onclick = () => {
    if (qrContainer.style.display === 'none') {
      qrContainer.style.display = 'flex';
      toggleQr.textContent = 'Hide QR';
    } else {
      qrContainer.style.display = 'none';
      toggleQr.textContent = 'Show QR';
    }
  };

  function checkUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const roomParam = params.get('room');
    if (roomParam) {
      roomInput.value = roomParam;
      setTimeout(() => connect(), 500);
    }
  }

  function getUserName() {
    return usernameInput.value.trim() || 'Web User';
  }

  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    
    let roomId = roomInput.value.trim();
    if (!roomId) {
      roomId = generateRoomId();
      roomInput.value = roomId;
    }
    
    const encodedRoom = encodeURIComponent(roomId);
    ws = new WebSocket(wsUrl(`/ws/${encodedRoom}`));
    ws.binaryType = 'arraybuffer';
    
    ws.onopen = () => { 
      log(`✓ Connected to room: ${roomId}`); 
      setStatus('Connected', true);
      showQRCode(roomId);
      
      const newUrl = `${location.origin}/?room=${encodedRoom}`;
      window.history.pushState({}, '', newUrl);
    };
    
    ws.onclose = () => { 
      log('✗ Disconnected'); 
      setStatus('Disconnected', false);
      qrSection.style.display = 'none';
    };
    
    ws.onerror = () => { 
      log('⚠ Connection error'); 
      setStatus('Error', false); 
    };
    
    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'msg') {
            log(`💬 [${data.sender || 'peer'}] ${data.text}`);
          } else if (data.type === 'file-meta') {
            beginReceiveFile(data);
          } else if (data.type === 'file-header') {
            prepareReceiveChunk(data);
          }
        } catch (e) {
          log(`📨 ${event.data}`);
        }
      } else if (event.data instanceof ArrayBuffer) {
        onBinaryChunk(event.data);
      }
    };
  }

  function disconnect() {
    if (ws) { 
      ws.close(); 
      ws = null; 
    }
  }

  connectBtn.onclick = connect;
  disconnectBtn.onclick = disconnect;

  sendMsgBtn.onclick = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const text = msgInput.value.trim();
    if (!text) return;
    ws.send(JSON.stringify({ 
      type: 'msg', 
      sender: getUserName(), 
      text 
    }));
    msgInput.value = '';
  };

  msgInput.onkeypress = (e) => {
    if (e.key === 'Enter') sendMsgBtn.click();
  };

  fileInput.onchange = (e) => {
    const fileName = e.target.files?.[0]?.name;
    if (fileName) {
      const label = document.querySelector('.file-label span');
      label.textContent = `Selected: ${fileName}`;
    }
  };

  let currentFileId = null;

  sendFileBtn.onclick = async () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      log('⚠ Not connected. Please connect first.');
      return;
    }
    const f = fileInput.files?.[0];
    if (!f) {
      log('⚠ No file selected');
      return;
    }

    const chunkSize = 256 * 1024;
    const totalChunks = Math.ceil(f.size / chunkSize);
    const fileId = (self.crypto?.randomUUID?.() || String(Date.now()) + Math.random().toString(16).slice(2));

    ws.send(JSON.stringify({
      type: 'file-meta',
      name: f.name,
      size: f.size,
      mime: f.type || 'application/octet-stream',
      totalChunks,
      fileId,
      sender: getUserName()
    }));

    log(`📤 Sending: ${f.name} (${(f.size / 1024 / 1024).toFixed(2)} MB)`);

    let sent = 0;
    for (let i = 0; i < totalChunks; i++) {
      const chunk = f.slice(i * chunkSize, Math.min((i + 1) * chunkSize, f.size));
      const arrayBuffer = await chunk.arrayBuffer();
      
      ws.send(JSON.stringify({
        type: 'file-header',
        fileId,
        idx: i,
        total: totalChunks,
        size: arrayBuffer.byteLength
      }));
      
      ws.send(arrayBuffer);
      
      sent += arrayBuffer.byteLength;
      const percent = (sent / f.size * 100).toFixed(1);
      sendProgEl.style.width = percent + '%';
      sendPercentEl.textContent = percent + '%';
    }
    
    log(`✓ File sent successfully`);
    setTimeout(() => {
      sendProgEl.style.width = '0%';
      sendPercentEl.textContent = '0%';
      fileInput.value = '';
      document.querySelector('.file-label span').textContent = 'Click to select file';
    }, 3000);
  };

  let pendingChunk = null;

  function beginReceiveFile(meta) {
    recvState.set(meta.fileId, {
      name: meta.name,
      mime: meta.mime || 'application/octet-stream',
      size: meta.size,
      total: meta.totalChunks,
      chunks: new Array(meta.totalChunks),
      received: 0
    });
    recvProgEl.style.width = '0%';
    recvPercentEl.textContent = '0%';
    log(`📥 Receiving: ${meta.name} from ${meta.sender || 'peer'} (${(meta.size / 1024 / 1024).toFixed(2)} MB)`);
  }

  function prepareReceiveChunk(header) {
    pendingChunk = header;
  }

  function onBinaryChunk(arrayBuffer) {
    if (!pendingChunk) return;
    
    const st = recvState.get(pendingChunk.fileId);
    if (!st) return;
    
    st.chunks[pendingChunk.idx] = new Uint8Array(arrayBuffer);
    st.received++;
    
    const percent = (st.received / st.total * 100).toFixed(1);
    recvProgEl.style.width = percent + '%';
    recvPercentEl.textContent = percent + '%';
    
    pendingChunk = null;
    
    if (st.received === st.total) {
      const blob = new Blob(st.chunks, { type: st.mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = st.name;
      a.textContent = st.name;
      downloadsEl.appendChild(a);
      log(`✓ File received: ${st.name}`);
      recvState.delete(pendingChunk?.fileId);
      
      setTimeout(() => {
        recvProgEl.style.width = '0%';
        recvPercentEl.textContent = '0%';
      }, 3000);
    }
  }

  checkUrlParams();
})();
