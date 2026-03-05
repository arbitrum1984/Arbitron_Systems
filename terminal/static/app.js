/**
 * @module static/app
 *
 * This module bootstraps the Arbitron Systems single-page client application.
 */

const { createApp, ref, onMounted, nextTick, watch } = Vue;

marked.setOptions({ gfm: true, breaks: true });

let maxZIndex = 100;
let offsetCounter = 0;
const sessionChartCounters = {}; // Track how many of each ticker have been opened this session

createApp({
    setup() {
        const input = ref('');
        const messages = ref([]);
        const favorites = ref([]);
        const chatSessions = ref([]);
        const currentChatId = ref(null);
        const isLoading = ref(false);
        const is3DLoaded = ref(false);
        const selected3DTicker = ref('SPY');

        const intelMessages = ref([]);
        const pizzaData = ref([]);

        const renderQueue = ref([]);
        const activeWidgets = ref([]); // Changed from Set to reactive array
        let isProcessingQueue = false;

        const showVoice = ref(false);
        const showFavorites = ref(false);
        const showSettings = ref(false);
        const newFav = ref('');
        const voiceStatusText = ref('Ready');

        // Trade Bot State
        const backtestList = ref([]);
        const selectedRunId = ref(null);
        const backtestData = ref(null);
        const backtestStartDate = ref('');
        const backtestEndDate = ref('');

        // Docker Logs State
        const selectedLogContainer = ref('arbitron_terminal');
        const containerLogs = ref('');
        const isLogsLoading = ref(false);

        const fetchLogs = async () => {
            if (document.getElementById('window-logs').style.display === 'none') return;
            isLogsLoading.value = true;
            try {
                const r = await fetch(`/api/logs/${selectedLogContainer.value}`);
                if (r.ok) {
                    const data = await r.json();
                    containerLogs.value = data.logs;
                }
            } catch (e) {
                containerLogs.value = "Error fetching logs: " + e.message;
            } finally {
                isLogsLoading.value = false;
                nextTick(() => {
                    const el = document.querySelector('.log-viewer-container');
                    if (el) el.scrollTop = el.scrollHeight;
                });
            }
        };

        const fetchBacktestList = async () => {
            try {
                const r = await fetch('/api/backtests');
                if (r.ok) backtestList.value = await r.json();
            } catch (e) {
                console.error("Backtest list fetch error:", e);
            }
        };

        const loadBacktestDetails = async (runId) => {
            selectedRunId.value = runId;
            backtestData.value = null;
            try {
                const r = await fetch(`/api/backtests/${runId}`);
                if (r.ok) {
                    const data = await r.json();
                    if (data.error) {
                        console.error("Backend returned error:", data.error);
                        alert("Error loading results: " + data.error);
                        selectedRunId.value = null;
                        return;
                    }
                    backtestData.value = data;
                    renderTradeBotCharts(data);
                } else {
                    console.error("API Error status:", r.status);
                    alert("Failed to fetch results from server.");
                }
            } catch (e) {
                console.error("Backtest detail fetch error:", e);
                alert("Connection failed while loading analytics.");
            }
        };

        const renderTradeBotCharts = (data) => {
            if (!data || !data.performance || !data.ic) {
                console.warn("Incomplete data for charts:", data);
                return;
            }

            nextTick(() => {
                try {
                    // Performance Chart
                    if (data.performance.dates && data.performance.dates.length > 0) {
                        const perfTraces = [
                            {
                                x: data.performance.dates,
                                y: data.performance.strategy_cum,
                                name: 'AI Strategy',
                                type: 'scatter',
                                mode: 'lines',
                                line: { color: '#0f0', width: 2 }
                            }
                        ];
                        if (data.performance.benchmark_cum) {
                            perfTraces.push({
                                x: data.performance.dates,
                                y: data.performance.benchmark_cum,
                                name: 'Benchmark',
                                type: 'scatter',
                                mode: 'lines',
                                line: { color: '#555', dash: 'dot' }
                            });
                        }
                        Plotly.newPlot('tb-chart-performance', perfTraces, {
                            paper_bgcolor: 'rgba(0,0,0,0)',
                            plot_bgcolor: 'rgba(0,0,0,0)',
                            xaxis: { gridcolor: '#111', tickfont: { color: '#666' } },
                            yaxis: { gridcolor: '#111', tickfont: { color: '#666' } },
                            margin: { l: 40, r: 20, t: 20, b: 40 },
                            showlegend: true,
                            legend: { font: { color: '#888' } }
                        }, { responsive: true, displayModeBar: false });
                    }

                    // IC Chart
                    if (data.ic.dates && data.ic.dates.length > 0) {
                        Plotly.newPlot('tb-chart-ic', [{
                            x: data.ic.dates,
                            y: data.ic.values,
                            type: 'bar',
                            marker: { color: '#0af', opacity: 0.6 }
                        }], {
                            paper_bgcolor: 'rgba(0,0,0,0)',
                            plot_bgcolor: 'rgba(0,0,0,0)',
                            xaxis: { gridcolor: '#111', tickfont: { color: '#666' } },
                            yaxis: { gridcolor: '#111', tickfont: { color: '#666' } },
                            margin: { l: 40, r: 20, t: 20, b: 40 }
                        }, { responsive: true, displayModeBar: false });
                    }
                } catch (err) {
                    console.error("Plotly rendering error:", err);
                }
            });
        };

        const triggerNewTraining = async () => {
            if (!confirm("Start full re-training pipeline? This will take ~2-3 minutes. You can check logs in 'quant_worker' container.")) return;
            try {
                const r = await fetch('/api/train/trigger', { method: 'POST' });
                const res = await r.json();
                if (res.status) {
                    alert("Training task dispatched to worker successfully!");
                } else {
                    alert("Error triggering training: " + (res.error || "Unknown error"));
                }
            } catch (e) {
                alert("Connection error while triggering training.");
            }
        };

        const runCustomBacktest = async () => {
            if (!backtestStartDate.value || !backtestEndDate.value) {
                alert("Please select both start and end dates.");
                return;
            }

            const start = new Date(backtestStartDate.value);
            const end = new Date(backtestEndDate.value);
            const today = new Date();
            const maxAllowedDate = new Date();
            maxAllowedDate.setDate(today.getDate() - 5);

            if (end > maxAllowedDate) {
                alert(`Maximum allowed end date is ${maxAllowedDate.toLocaleDateString()} (today - 5 days).`);
                return;
            }

            if (start >= end) {
                alert("Start date must be before end date.");
                return;
            }

            try {
                const r = await fetch('/api/backtests/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        start_date: backtestStartDate.value,
                        end_date: backtestEndDate.value
                    })
                });
                const res = await r.json();
                alert("Custom backtest started! It will appear in the list once finished.");
                fetchBacktestList();
            } catch (e) {
                alert("Error starting backtest.");
            }
        };


        /**
         * Toggle visibility of a named floating window.
         *
         * Shows the element with the given id (setting `display` to
         * `flex`) and brings it to the foreground, or hides it if it
         * is currently visible.
         *
         * @param {string} id - DOM id of the window element to toggle.
         * @returns {void}
         */
        const saveWindowLayout = (id, layout) => {
            const allLayouts = JSON.parse(localStorage.getItem('arbitron_window_layouts') || '{}');
            allLayouts[id] = { ...allLayouts[id], ...layout };
            localStorage.setItem('arbitron_window_layouts', JSON.stringify(allLayouts));
        };

        const loadWindowLayout = (id) => {
            const allLayouts = JSON.parse(localStorage.getItem('arbitron_window_layouts') || '{}');
            return allLayouts[id];
        };

        const toggleWindow = (id) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (el.style.display === 'none' || el.style.display === '') {
                el.style.display = 'flex';
                bringToFront(el);
                saveWindowLayout(id, { visible: true });

                // Multi-modal data fetch
                if (id === 'window-tradebot') fetchBacktestList();
                if (id === 'window-fred') fetchSavedFredSeries();
                if (id === 'window-edgar') fetchSavedCompanies();
                if (id === 'window-logs') fetchLogs();
            } else {
                el.style.display = 'none';
                saveWindowLayout(id, { visible: false });
            }
        };

        onMounted(async () => {
            await fetchFavorites();
            await fetchChatSessions();

            const savedSession = localStorage.getItem('arbitron_last_session');
            if (savedSession) await switchChat(savedSession);
            else createNewChat();

            nextTick(() => {
                ['window-intel', 'window-3d', 'window-pizza', 'window-edgar', 'window-fred', 'window-tradebot', 'window-logs'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) setupWindow(el);
                });

                // Fetch saved items
                fetchSavedCompanies();
                fetchSavedFredSeries();
                fetchBacktestList();
                loadActiveCharts(); // Restore open charts on load
            });

            await fetchIntelStream();
            setInterval(fetchIntelStream, 3000);

            await fetchPizzaData();
            setInterval(fetchPizzaData, 5000);

            setInterval(fetchBacktestList, 15000);
        });

        const saveActiveCharts = () => {
            const charts = [];
            document.querySelectorAll('.chart-card[id^="tv-card-"]').forEach(el => {
                const ticker = el.querySelector('.chart-title-bar span').innerText;
                charts.push({ id: el.id, ticker: ticker });
            });
            localStorage.setItem('arbitron_active_charts', JSON.stringify(charts));
        };

        const loadActiveCharts = () => {
            const saved = JSON.parse(localStorage.getItem('arbitron_active_charts') || '[]');
            saved.forEach(c => {
                // If the saved item has an ID, we use it to restore layout
                renderQueue.value.push({ ticker: c.ticker, forcedId: c.id });
            });
            processQueue();
        };

        /**
         * Fetch the live "INTEL_STREAM" messages from the server and
         * update the local reactive `intelMessages` array.
         *
         * Errors are logged to the console but do not throw.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetchIntelStream = async () => {
            try {
                const r = await fetch('/api/chats/INTEL_STREAM/messages');
                if (r.ok) {
                    const data = await r.json();
                    intelMessages.value = data.reverse();
                }
            } catch (e) {
                console.error("Intel Stream Error:", e);
            }
        };

        /**
         * Fetch synthetic or proxied pizza occupancy data from
         * `/api/pizza` and update the reactive `pizzaData` reference.
         *
         * This endpoint is expected to return the same normalized
         * structure produced by the server-side `PizzaService`.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetchPizzaData = async () => {
            try {
                // Стучимся на новый роут, который ты добавил в main.py
                const r = await fetch('/api/pizza');
                if (r.ok) {
                    pizzaData.value = await r.json();
                }
            } catch (e) {
                console.error("Pizza fetch error:", e);
            }
        };



        /**
         * Prepare a floating window element for interaction.
         *
         * Adds drag/resize behavior and ensures the window is
         * brought to the front when focused.
         *
         * @param {HTMLElement} el - Root element of the window.
         * @returns {void}
         */
        const setupWindow = (el) => {
            if (!el) return;
            makeDraggable(el);
            attachWindowResizer(el);
            el.onmousedown = () => bringToFront(el);

            // Apply saved layout
            const saved = loadWindowLayout(el.id);
            if (saved) {
                if (saved.top) el.style.top = saved.top;
                if (saved.left) el.style.left = saved.left;
                if (saved.width) el.style.width = saved.width;
                if (saved.height) el.style.height = saved.height;

                // Only override display if visibility is explicitly saved
                if (saved.visible === true) el.style.display = 'flex';
                else if (saved.visible === false) el.style.display = 'none';
            }
        };

        /**
         * Make a container draggable using its `.chart-title-bar` as
         * the drag handle.
         *
         * This function mutates element `style.top` and `style.left`
         * and toggles helper CSS classes during the drag operation.
         *
         * @param {HTMLElement} elmnt - Element to make draggable.
         * @returns {void}
         */
        const makeDraggable = (elmnt) => {
            let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
            const header = elmnt.querySelector('.chart-title-bar');

            if (header) {
                header.onmousedown = dragMouseDown;
            }

            function dragMouseDown(e) {
                // Игнорируем клики по кнопкам закрытия или селектам
                if (e.target.closest('.chart-remove-btn') || e.target.closest('select')) return;

                e.preventDefault();
                pos3 = e.clientX;
                pos4 = e.clientY;

                elmnt.classList.add('is-dragging');
                document.body.classList.add('window-dragging'); // <--- ВАЖНО ДЛЯ CSS БЛЮРА
                bringToFront(elmnt);

                document.onmouseup = closeDragElement;
                document.onmousemove = elementDrag;
            }

            function elementDrag(e) {
                e.preventDefault();
                pos1 = pos3 - e.clientX;
                pos2 = pos4 - e.clientY;
                pos3 = e.clientX;
                pos4 = e.clientY;

                elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
                elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
            }

            function closeDragElement() {
                document.onmouseup = null;
                document.onmousemove = null;
                elmnt.classList.remove('is-dragging');
                document.body.classList.remove('window-dragging'); // <--- УБИРАЕМ БЛЮР

                // Save position
                saveWindowLayout(elmnt.id, {
                    top: elmnt.style.top,
                    left: elmnt.style.left,
                    visible: true // Ensure we don't vanish on reload
                });
            }
        };


        /**
         * Attach a bottom-right resize handle to a floating window.
         *
         * The handler constrains minimum width/height to avoid
         * creating unusable windows and toggles CSS classes for UX.
         *
         * @param {HTMLElement} el - Window element to make resizable.
         * @returns {void}
         */
        const attachWindowResizer = (el) => {
            if (!el) return;
            if (el.querySelector('.window-resize-handle')) return;

            const handle = document.createElement('div');
            handle.className = 'window-resize-handle';
            el.appendChild(handle);

            let startX, startY, startW, startH;

            const onMouseDown = (e) => {
                e.stopPropagation();
                e.preventDefault();

                el.classList.add('is-resizing');

                // --- ДОБАВЬ ЭТИ ДВЕ СТРОКИ ---
                el.classList.add('is-dragging'); // Чтобы текущее окно не блюрилось
                document.body.classList.add('window-dragging'); // Чтобы включить "Щит" на всех iframe
                // -----------------------------

                startX = e.clientX;
                startY = e.clientY;
                startW = el.offsetWidth;
                startH = el.offsetHeight;

                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp, { once: true });
            };

            const onMouseMove = (e) => {
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                el.style.width = Math.max(200, startW + dx) + 'px';
                el.style.height = Math.max(150, startH + dy) + 'px';
            };

            const onMouseUp = () => {
                el.classList.remove('is-resizing');
                el.classList.remove('is-dragging');
                document.body.classList.remove('window-dragging');

                document.removeEventListener('mousemove', onMouseMove);

                // Save size
                saveWindowLayout(el.id, {
                    width: el.style.width,
                    height: el.style.height,
                    visible: true
                });
            };

            handle.addEventListener('mousedown', onMouseDown);
        };

        /**
         * Increase the global stacking context and mark a window as
         * active so it visually appears above siblings.
         *
         * @param {HTMLElement} el - Element to bring forward.
         * @returns {void}
         */
        const bringToFront = (el) => {
            maxZIndex++;
            el.style.zIndex = maxZIndex;
            document.querySelectorAll('.chart-card').forEach(c => c.classList.remove('active-window'));
            el.classList.add('active-window');
        };

        /**
         * Enable column resizing of the left chat panel via the
         * central vertical resizer element with id `resizer`.
         *
         * The implementation attaches mouse handlers and enforces
         * sensible minimum/maximum widths for the panel.
         *
         * @returns {void}
         */
        const makeResizable = () => {
            const resizer = document.getElementById('resizer');
            const sidebar = document.getElementById('chat-panel');
            if (!resizer || !sidebar) return;
            resizer.addEventListener('mousedown', (e) => {
                e.preventDefault();
                document.addEventListener('mousemove', resize);
                document.addEventListener('mouseup', stopResize);
            });
            function resize(e) {
                const newWidth = e.clientX - 50;
                if (newWidth > 200 && newWidth < 800) sidebar.style.width = newWidth + 'px';
            }
            function stopResize() {
                document.removeEventListener('mousemove', resize);
                document.removeEventListener('mouseup', stopResize);
            }
        };

        /**
         * Toggle the 3D quant visualization window.
         *
         * @returns {void}
         */
        const show3DWindow = () => toggleWindow('window-3d');

        /**
         * Fetch and render the 3D volatility surface for the
         * currently-selected ticker using the server-side API.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetch3DData = async () => {
            const r = await fetch(`/api/quant/surface?ticker=${selected3DTicker.value}`);
            const fig = await r.json();
            Plotly.newPlot('quant-chart', fig.data, fig.layout, { responsive: true, displayModeBar: false });
            is3DLoaded.value = true;
        };

        watch(selected3DTicker, () => { if (is3DLoaded.value) fetch3DData(); });

        watch(favorites, (newVal, oldVal) => {
            // Auto-open only if no window for this ticker exists at all
            newVal.forEach(t => {
                if (!document.querySelector(`[id^="tv-card-${t}"]`)) {
                    renderQueue.value.push(t);
                }
            });
            // When removed from favorites, remove ALL window instances for that ticker
            if (oldVal) {
                oldVal.forEach(t => {
                    if (!newVal.includes(t)) {
                        document.querySelectorAll(`[id^="tv-card-${t}"]`).forEach(el => {
                            removeWidgetFromDOM(el.id);
                        });
                    }
                });
            }
            processQueue();
        }, { deep: true });

        /**
         * Process the render queue for TradingView widgets serially.
         *
         * Ensures only a single widget is created at a time to avoid
         * excessive layout thrash. The function is re-entrant-safe.
         *
         * @async
         * @returns {Promise<void>}
         */
        const processQueue = async () => {
            if (isProcessingQueue || renderQueue.value.length === 0) return;
            isProcessingQueue = true;
            const item = renderQueue.value.shift();
            // Handle both simple strings and objects with forcedId
            if (typeof item === 'string') {
                createWidgetDOM(item);
            } else {
                createWidgetDOM(item.ticker, item.forcedId);
            }
            setTimeout(() => { isProcessingQueue = false; processQueue(); }, 300);
        };

        /**
         * Create and insert a TradingView widget card for a ticker.
         *
         * If a widget for the ticker already exists this function
         * will be a no-op. The card is wired with removal and drag
         * handlers and the TradingView library is invoked to render
         * the chart.
         *
         * @param {string} ticker - Ticker symbol to render.
         * @returns {void}
         */
        const createWidgetDOM = (ticker, forcedId = null) => {
            const container = document.getElementById('desktop-area');
            if (!container) return;

            // Use forcedId if provided (for persistence), otherwise generate stable ID
            let cardId = forcedId;
            if (!cardId) {
                if (!sessionChartCounters[ticker]) sessionChartCounters[ticker] = 0;
                cardId = `tv-card-${ticker}-${sessionChartCounters[ticker]}`;
                sessionChartCounters[ticker]++;

                // Safety check: if somehow this ID exists, increment until free
                while (document.getElementById(cardId)) {
                    cardId = `tv-card-${ticker}-${sessionChartCounters[ticker]}`;
                    sessionChartCounters[ticker]++;
                }
            } else if (document.getElementById(cardId)) {
                return;
            }

            const div = document.createElement('div');
            div.className = 'chart-card';
            div.id = cardId;
            offsetCounter++; if (offsetCounter > 10) offsetCounter = 0;
            div.style.top = (100 + offsetCounter * 30) + 'px';
            div.style.left = (100 + offsetCounter * 30) + 'px';
            const widgetId = `tv-${ticker}-${Math.random().toString(36).substr(2, 5)}`;
            div.innerHTML = `
                <div class="chart-title-bar">
                    <span>${ticker}</span>
                    <span class="chart-remove-btn"><svg class="del-icon-svg" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></span>
                </div>
                <div id="${widgetId}" class="tv-widget-container"></div>
            `;
            container.appendChild(div);
            setupWindow(div);
            // Ensure the close button uses the unique cardId for this instance
            div.querySelector('.chart-remove-btn').onclick = () => removeWidgetFromDOM(cardId);
            new TradingView.widget({ "autosize": true, "symbol": ticker, "interval": "D", "theme": "dark", "container_id": widgetId });
            bringToFront(div);
            activeWidgets.value.push(cardId);
            saveActiveCharts(); // Persist the list
        };

        /**
         * Check if a ticker is currently active in the dashboard (exists in DOM).
         */
        const isTickerActive = (ticker) => {
            return activeWidgets.value.includes(ticker) || !!document.getElementById(`tv-card-${ticker}`);
        };
        /**
         * Open a ticker chart (forced create).
         */
        const openTickerChart = (ticker) => {
            renderQueue.value.push(ticker);
            processQueue();
        };

        const removeWidgetFromDOM = (tickerOrId) => {
            // Smarter lookup: check if it's already an ID or needs prefix
            let el = document.getElementById(tickerOrId);
            if (!el && !tickerOrId.startsWith('tv-card-')) {
                el = document.getElementById(`tv-card-${tickerOrId}`);
            }

            if (el) el.remove();
            activeWidgets.value = activeWidgets.value.filter(t => t !== tickerOrId);
            saveActiveCharts(); // Update persistence
        };

        /**
         * Fetch the list of available chat sessions from the server.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetchChatSessions = async () => { try { const r = await fetch('/api/chats'); if (r.ok) chatSessions.value = await r.json(); } catch (e) { } };

        /**
         * Create a new local chat session identifier and persist it.
         *
         * @async
         * @returns {Promise<void>}
         */
        const createNewChat = async () => {
            const newId = 'session_' + Date.now().toString().slice(-4);
            currentChatId.value = newId; messages.value = [];
            localStorage.setItem('arbitron_last_session', newId); await fetchChatSessions();
        };

        /**
         * Switch the UI to an existing chat session and load messages.
         *
         * @param {string} sid - Session identifier to switch to.
         * @async
         * @returns {Promise<void>}
         */
        const switchChat = async (sid) => {
            currentChatId.value = sid; localStorage.setItem('arbitron_last_session', sid);
            isLoading.value = true;
            try { const r = await fetch(`/api/chats/${sid}/messages`); if (r.ok) messages.value = await r.json(); else createNewChat(); } catch (e) { } finally { isLoading.value = false; }
        };

        /**
         * Delete a chat session after user confirmation and refresh list.
         *
         * @param {string} sid - Session identifier to delete.
         * @async
         * @returns {Promise<void>}
         */
        const deleteChat = async (sid) => { if (!confirm("Delete?")) return; await fetch(`/api/chats/${sid}`, { method: 'DELETE' }); await fetchChatSessions(); if (currentChatId.value === sid) createNewChat(); };

        /**
         * Send the current input as a chat message to the server and
         * append the assistant's response to the local message list.
         *
         * This function performs optimistic UI updates and scrolls the
         * chat box to the bottom after messages change.
         *
         * @async
         * @returns {Promise<void>}
         */
        const sendMessage = async () => {
            const txt = input.value.trim(); if (!txt) return;
            messages.value.push({ role: 'user', content: txt }); input.value = ''; isLoading.value = true; nextTick(() => { const el = document.getElementById('chat-box'); if (el) el.scrollTop = el.scrollHeight; });
            const fd = new FormData(); fd.append('query_text', txt); fd.append('session_id', currentChatId.value);
            try {
                const r = await fetch('/api/query', { method: 'POST', body: fd }); const d = await r.json();
                messages.value.push({ role: 'assistant', content: d.answer_text }); fetchChatSessions();
                if (d.ticker) { selected3DTicker.value = d.ticker; if (d.answer_text.includes('[TRADINGVIEW_WIDGET]')) nextTick(() => injectChatWidget(d.ticker)); }
            } catch (e) { messages.value.push({ role: 'assistant', content: e.message }); } finally { isLoading.value = false; nextTick(() => { const el = document.getElementById('chat-box'); if (el) el.scrollTop = el.scrollHeight; }); }
        };

        /**
         * Inject a TradingView widget placeholder created by assistant
         * responses into the DOM for a given ticker.
         *
         * @param {string} t - Ticker symbol to render in the widget.
         * @returns {void}
         */
        const injectChatWidget = (t) => { document.querySelectorAll('.chat-widget-placeholder:empty').forEach(el => { const id = 'tv-chat-' + Math.random().toString(36).substring(7); el.id = id; new TradingView.widget({ "autosize": true, "symbol": t, "interval": "D", "theme": "dark", "style": "1", "container_id": id }); }); };

        /**
         * Convert markdown text to HTML and replace special widget
         * tokens with placeholder containers.
         *
         * @param {string} t - Raw markdown/text to render.
         * @returns {string} HTML string safe for insertion via `v-html`.
         */
        const renderMarkdown = (t) => {
            if (!t) return '';
            let h = marked.parse(t);
            // Open links in new tab
            h = h.replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ');

            if (h.includes('[TRADINGVIEW_WIDGET]')) {
                h = h.replace(/<p>\[TRADINGVIEW_WIDGET\]<\/p>|\[TRADINGVIEW_WIDGET\]/g,
                    '<div class="chat-widget-placeholder" style="width:100%; height:300px; margin-top:10px; border:1px solid #333;"></div>');
            }
            return h;
        };

        /**
         * Refresh the user's favorite tickers from the server.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetchFavorites = async () => { try { const r = await fetch('/api/favorites'); if (r.ok) favorites.value = await r.json(); } catch (e) { } };

        /**
         * Add a new ticker to the user's favorites via the API.
         *
         * @async
         * @returns {Promise<void>}
         */
        const addFavorite = async () => { if (!newFav.value) return; await fetch('/api/favorites', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ticker: newFav.value.toUpperCase() }) }); await fetchFavorites(); newFav.value = ''; };

        /**
         * Remove a ticker from the user's favorites and refresh state.
         *
         * @param {string} t - Ticker symbol to remove.
         * @async
         * @returns {Promise<void>}
         */
        const removeFavorite = async (t) => { await fetch(`/api/favorites/${t}`, { method: 'DELETE' }); await fetchFavorites(); };

        /**
         * Open the voice input modal; placeholder for voice UX.
         *
         * @returns {void}
         */
        const toggleVoice = () => { showVoice.value = true; };

        const savedCompanies = ref([]);
        const selectedEdgarTicker = ref(null);
        const isEdgarLoading = ref(false);
        const edgarData = ref(null);
        const newEdgarTicker = ref('');

        /**
         * Fetch the list of saved companies (tickers) for the EDGAR sidebar.
         */
        const fetchSavedCompanies = async () => {
            try {
                const r = await fetch('/api/edgar/saved/list');
                if (r.ok) {
                    const data = await r.json();
                    savedCompanies.value = data.tickers || [];
                }
            } catch (e) {
                console.error("Error fetching saved companies:", e);
            }
        };

        // --- FRED Methods ---
        const savedFredSeries = ref([]);
        const newFredSeries = ref('');
        const currentFredSeries = ref(null);
        const activeFredCharts = ref([]);
        const isFredLoading = ref(false);

        const fetchSavedFredSeries = async () => {
            try {
                const response = await fetch('/api/fred/saved');
                if (response.ok) {
                    const data = await response.json();
                    savedFredSeries.value = data.series || [];
                }
            } catch (e) {
                console.error("Error fetching saved FRED series:", e);
            }
        };

        const addFredSeries = async () => {
            if (!newFredSeries.value) return;
            const id = newFredSeries.value.trim().toUpperCase();
            await loadFredSeries(id);
            newFredSeries.value = '';
            // Refresh list
            await fetchSavedFredSeries();
        };

        const loadFredSeries = async (seriesId) => {
            currentFredSeries.value = seriesId;
            activeFredCharts.value = []; // Clear current view
            isFredLoading.value = true;

            try {
                const response = await fetch(`/api/fred/series/${seriesId}`);
                if (!response.ok) throw new Error("Failed to fetch FRED data");
                const data = await response.json();

                // Format for Plotly
                // data is array of {date: '...', value: 123.45}
                const dates = data.map(d => d.date);
                const values = data.map(d => d.value);

                activeFredCharts.value.push({
                    id: seriesId,
                    data: [{
                        x: dates,
                        y: values,
                        type: 'scatter',
                        mode: 'lines',
                        name: seriesId,
                        line: { color: '#00ff00', width: 2 }
                    }],
                    layout: {
                        title: { text: seriesId, font: { color: '#00ff00' } },
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        xaxis: {
                            gridcolor: '#333',
                            tickfont: { color: '#00ff00' }
                        },
                        yaxis: {
                            gridcolor: '#333',
                            tickfont: { color: '#00ff00' }
                        },
                        margin: { l: 40, r: 20, t: 40, b: 40 },
                        showlegend: false
                    }
                });

                // Render chart
                nextTick(() => {
                    // The HTML element ID is the seriesId (e.g., "GDP") based on :id="chart.id"
                    Plotly.newPlot(seriesId, activeFredCharts.value[0].data, activeFredCharts.value[0].layout, {
                        displayModeBar: false,
                        responsive: true,
                        scrollZoom: false
                    });
                });

            } catch (e) {
                console.error("Error loading FRED series:", e);
                alert("Could not load series. Check ID.");
            } finally {
                isFredLoading.value = false;
            }
        };

        /**
         * Search for a new ticker, fetch data, and add to list.
         */
        const searchEdgarTicker = async () => {
            const t = newEdgarTicker.value.trim().toUpperCase();
            console.log("Searching ticker:", t);
            if (!t) return;

            newEdgarTicker.value = ''; // Clear input immediately
            await loadEdgarData(t);
            await fetchSavedCompanies(); // Refresh list to include the new one
        };

        /**
         * Load SEC data for a ticker and render charts.
         */
        const loadEdgarData = async (ticker) => {
            selectedEdgarTicker.value = ticker;
            isEdgarLoading.value = true;
            edgarData.value = null; // Clear old data

            try {
                const r = await fetch(`/api/edgar/${ticker}`);
                if (r.ok) {
                    const data = await r.json();
                    edgarData.value = data;
                    renderEdgarCharts(data);
                } else {
                    alert(`Failed to fetch data for ${ticker}. Check console.`);
                    console.error(await r.text());
                }
            } catch (e) {
                console.error("Error fetching SEC data:", e);
                alert("Error fetching SEC data");
            } finally {
                isEdgarLoading.value = false;
            }
        };

        /**
         * Filter and plot financial metrics using Plotly.
         */
        const activeEdgarCharts = ref([]);

        /**
         * Filter and plot financial metrics using Plotly.
         */
        const renderEdgarCharts = (facts) => {
            if (!facts || facts.length === 0) return;

            // Define metrics configuration
            // We check multiple potential tags for each metric to handle taxonomy variations
            const metrics = [
                { id: 'ec-rev', title: 'Revenue', tags: ['Revenue', 'Revenues', 'RevenueFromContractWithCustomer'] },
                { id: 'ec-netinc', title: 'Net Income', tags: ['NetIncomeLoss', 'ProfitLoss'] },
                { id: 'ec-opinc', title: 'Operating Income', tags: ['OperatingIncomeLoss'] },
                { id: 'ec-eps', title: 'EPS (Basic)', tags: ['EarningsPerShareBasic'] },
                { id: 'ec-assets', title: 'Total Assets', tags: ['Assets'] },
                { id: 'ec-liab', title: 'Total Liabilities', tags: ['Liabilities'] },
                { id: 'ec-equity', title: 'Stockholders Equity', tags: ['StockholdersEquity'] },
                { id: 'ec-cash', title: 'Cash & Equivalents', tags: ['CashAndCashEquivalents'] }
            ];

            // 1. Identify which metrics have data
            const availableCharts = [];

            metrics.forEach(m => {
                // Find matching facts for any of the tags
                // Filtering for '10-K' usually gives annual trend, '10-Q' is quarterly.
                const matchingFacts = facts.filter(f =>
                    m.tags.some(t => f.tag.includes(t)) &&
                    (f.form === '10-K' || f.form === '10-Q')
                );

                if (matchingFacts.length > 0) {
                    // Sort by date
                    matchingFacts.sort((a, b) => new Date(a.period) - new Date(b.period));

                    availableCharts.push({
                        id: m.id,
                        title: m.title,
                        data: matchingFacts
                    });
                }
            });

            // 2. Update reactive state to render DOM elements
            activeEdgarCharts.value = availableCharts;

            // 3. Plot charts after DOM update
            nextTick(() => {
                availableCharts.forEach(chart => {
                    const trace = {
                        x: chart.data.map(d => d.period),
                        y: chart.data.map(d => d.value),
                        type: 'bar',
                        name: chart.title,
                        marker: { color: '#00A3E0' }
                    };

                    const layout = {
                        title: { text: chart.title, font: { color: '#ddd' } },
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        xaxis: { color: '#888', type: 'category' }, // Category ensures dates don't get wonky
                        yaxis: { color: '#888' },
                        margin: { t: 40, b: 40, l: 60, r: 20 },
                        height: 300
                    };

                    Plotly.newPlot(chart.id, [trace], layout, {
                        responsive: true,
                        displayModeBar: false,
                        scrollZoom: false
                    });
                });
            });
        };


        return {
            input, messages, favorites, chatSessions, currentChatId, isLoading, is3DLoaded,
            showVoice, showFavorites, showSettings, newFav, voiceStatusText, selected3DTicker,
            intelMessages, pizzaData,
            savedCompanies, selectedEdgarTicker, isEdgarLoading, newEdgarTicker, activeEdgarCharts, fetchSavedCompanies, loadEdgarData, searchEdgarTicker,
            savedFredSeries, newFredSeries, currentFredSeries, activeFredCharts, isFredLoading, fetchSavedFredSeries, addFredSeries, loadFredSeries, // FRED Exports
            openTickerChart, // Simplified Watchlist Export
            createNewChat, switchChat, deleteChat, sendMessage, renderMarkdown, show3DWindow,
            fetch3DData, addFavorite, removeFavorite, toggleVoice, toggleWindow,
            backtestList, selectedRunId, backtestData, fetchBacktestList, loadBacktestDetails, triggerNewTraining,
            backtestStartDate, backtestEndDate, runCustomBacktest,
            selectedLogContainer, containerLogs, isLogsLoading, fetchLogs
        };
    }
}).mount('#app');