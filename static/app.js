function radioApp() {
    return {
        // State
        state: {
            freq: 14074000,
            mode: 'USB',
            smeter: -100,
            filter_width: 2400,
        },
        connectionStatus: 'disconnected',
        step: 1000,
        ws: null,

        // Constants
        modes: ['LSB', 'USB', 'CW', 'AM', 'FM', 'DATA'],
        steps: [
            { label: '10', value: 10 },
            { label: '100', value: 100 },
            { label: '1k', value: 1000 },
            { label: '10k', value: 10000 },
            { label: '100k', value: 100000 },
        ],

        // Computed
        get smeterPercent() {
            // Convert dBm (-120 to -20) to percentage
            const min = -120;
            const max = -20;
            const clamped = Math.max(min, Math.min(max, this.state.smeter));
            return ((clamped - min) / (max - min)) * 100;
        },

        // Methods
        init() {
            this.connect();
        },

        connect() {
            const credentials = this.getCredentials();
            if (!credentials) {
                this.connectionStatus = 'disconnected';
                return;
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws?token=${credentials}`;

            this.ws = new WebSocket(wsUrl);
            this.connectionStatus = 'reconnecting';

            this.ws.onopen = () => {
                this.connectionStatus = 'connected';
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.ws.onclose = () => {
                this.connectionStatus = 'disconnected';
                // Reconnect after 3 seconds
                setTimeout(() => this.connect(), 3000);
            };

            this.ws.onerror = () => {
                this.connectionStatus = 'disconnected';
            };
        },

        getCredentials() {
            // Get from URL or prompt
            const params = new URLSearchParams(window.location.search);
            let token = params.get('auth');

            if (!token) {
                // Credentials come from HTTP Basic Auth header
                // We'll extract them from a meta tag or prompt
                token = sessionStorage.getItem('radioAuth');
                if (!token) {
                    const user = prompt('Username:');
                    const pass = prompt('Password:');
                    if (user && pass) {
                        token = `${user}:${pass}`;
                        sessionStorage.setItem('radioAuth', token);
                    }
                }
            }

            return token;
        },

        handleMessage(data) {
            switch (data.type) {
                case 'state':
                    this.state = { ...this.state, ...data };
                    break;
                case 'ack':
                    console.log('Command acknowledged:', data.cmd, data.success);
                    break;
                case 'error':
                    console.error('Error:', data.message);
                    alert('Error: ' + data.message);
                    break;
            }
        },

        sendCommand(cmd, value) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ cmd, value }));
            }
        },

        setMode(mode) {
            this.sendCommand('set_mode', mode);
        },

        setFreq(freq) {
            this.sendCommand('set_freq', freq);
        },

        handleWheel(event) {
            const delta = event.deltaY < 0 ? this.step : -this.step;
            const newFreq = this.state.freq + delta;
            this.setFreq(newFreq);
            // Optimistic update
            this.state.freq = newFreq;
        },

        formatFreq(hz) {
            // Format as XX.XXX.XXX
            const str = hz.toString().padStart(8, '0');
            const mhz = str.slice(0, -6) || '0';
            const khz = str.slice(-6, -3);
            const h = str.slice(-3);
            return `${mhz}.${khz}.${h}`;
        },
    };
}
