function radioApp() {
    return {
        // State
        state: {
            freq: 14074000,
            mode: 'USB',
            smeter: -100,
            filter_width: 2400,
            rf_gain: 80,
            power: 50,
            agc: 'MED',
            break_in: false,
            rit: 0,
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
        bands: [
            { label: '160m', freq: 1810000 },   // CW edge
            { label: '80m', freq: 3500000 },
            { label: '40m', freq: 7000000 },
            { label: '30m', freq: 10100000 },
            { label: '20m', freq: 14000000 },
            { label: '17m', freq: 18068000 },
            { label: '15m', freq: 21000000 },
            { label: '12m', freq: 24890000 },
            { label: '10m', freq: 28000000 },
            { label: '6m', freq: 50000000 },
        ],
        agcModes: ['OFF', 'SLOW', 'MED', 'FAST'],

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

        setBand(freq) {
            this.setFreq(freq);
            // Optimistic update
            this.state.freq = freq;
        },

        setAGC(mode) {
            this.sendCommand('set_agc', mode);
        },

        setRFGain(value) {
            this.sendCommand('set_rf_gain', parseInt(value));
            this.state.rf_gain = parseInt(value);
        },

        setPower(value) {
            this.sendCommand('set_power', parseInt(value));
            this.state.power = parseInt(value);
        },

        triggerSpot() {
            // Momentary action - trigger spot to center CW signal
            this.sendCommand('set_spot', true);
        },

        setBreakIn(enabled) {
            this.sendCommand('set_break_in', enabled);
            this.state.break_in = enabled;
        },

        setRIT(offset) {
            this.sendCommand('set_rit', offset);
            this.state.rit = offset;
        },

        adjustRIT(delta) {
            const newRIT = this.state.rit + delta;
            this.setRIT(newRIT);
        },

        handleWheel(event) {
            const delta = event.deltaY < 0 ? this.step : -this.step;
            const newFreq = this.state.freq + delta;
            this.setFreq(newFreq);
            // Optimistic update
            this.state.freq = newFreq;
        },

        promptFrequency() {
            const input = prompt('Inserisci frequenza (es: 14.074 o 14074000):');
            if (!input) return;

            // Parse frequency - support multiple formats
            let freq = input.replace(/[^\d.]/g, ''); // Remove non-numeric except dots

            // If contains dot, assume MHz format
            if (freq.includes('.')) {
                freq = parseFloat(freq) * 1000000;
            } else {
                freq = parseInt(freq);
                // If less than 1 million, assume kHz
                if (freq < 1000000) {
                    freq = freq * 1000;
                }
            }

            // Validate range (HF: 1.8-30 MHz, VHF: 50-54 MHz, UHF: 144-148 MHz, etc)
            if (freq < 100000 || freq > 2000000000) {
                alert('Frequenza non valida. Range: 0.1 - 2000 MHz');
                return;
            }

            this.setFreq(freq);
            this.state.freq = freq;
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
