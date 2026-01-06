/**
 * @module static/app
 *
 * This module bootstraps the Arbitron Systems single-page client application.
 */

const { createApp, ref, onMounted, nextTick, watch } = Vue;

marked.setOptions({ gfm: true, breaks: true });

let maxZIndex = 100;
let offsetCounter = 0;

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
        const activeWidgets = new Set();
        let isProcessingQueue = false;

        const showVoice = ref(false);
        const showFavorites = ref(false);
        const showSettings = ref(false);
        const newFav = ref('');
        const voiceStatusText = ref('Ready');

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
        const toggleWindow = (id) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (el.style.display === 'none' || el.style.display === '') {
                el.style.display = 'flex';
                bringToFront(el);
            } else {
                el.style.display = 'none';
            }
        };

        onMounted(async () => {
            await fetchFavorites();
            await fetchChatSessions();
            
            const savedSession = localStorage.getItem('arbitron_last_session');
            if (savedSession) await switchChat(savedSession);
            else createNewChat();

            nextTick(() => {
                ['window-intel', 'window-3d', 'window-pizza'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) setupWindow(el);
                });
            });

            await fetchIntelStream();
            setInterval(fetchIntelStream, 30000);

            await fetchPizzaData();             
            setInterval(fetchPizzaData, 5000);  

            makeResizable();
        });

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
            newVal.forEach(t => { if (!activeWidgets.has(t)) renderQueue.value.push(t); });
            if (oldVal) oldVal.forEach(t => { if (!newVal.includes(t)) removeWidgetFromDOM(t); });
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
            createWidgetDOM(renderQueue.value.shift());
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
        const createWidgetDOM = (ticker) => {
            const container = document.getElementById('desktop-area');
            if (!container || document.getElementById(`card-${ticker}`)) return;
            const div = document.createElement('div');
            div.className = 'chart-card';
            div.id = `card-${ticker}`;
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
            div.querySelector('.chart-remove-btn').onclick = () => removeFavorite(ticker);
            new TradingView.widget({"autosize": true, "symbol": ticker, "interval": "D", "theme": "dark", "container_id": widgetId});
            bringToFront(div);
            activeWidgets.add(ticker);
        };

        /**
         * Remove a previously-created widget card identified by ticker.
         *
         * Safe to call even when the element does not exist.
         *
         * @param {string} ticker - Ticker symbol whose widget should be removed.
         * @returns {void}
         */
        const removeWidgetFromDOM = (ticker) => {
            const el = document.getElementById(`card-${ticker}`);
            if (el) el.remove();
            activeWidgets.delete(ticker);
        };

        /**
         * Fetch the list of available chat sessions from the server.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetchChatSessions = async () => { try { const r = await fetch('/api/chats'); if (r.ok) chatSessions.value = await r.json(); } catch (e) {} };

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
            try { const r = await fetch(`/api/chats/${sid}/messages`); if(r.ok) messages.value = await r.json(); else createNewChat(); } catch(e){} finally { isLoading.value = false; } 
        };

        /**
         * Delete a chat session after user confirmation and refresh list.
         *
         * @param {string} sid - Session identifier to delete.
         * @async
         * @returns {Promise<void>}
         */
        const deleteChat = async (sid) => { if(!confirm("Delete?")) return; await fetch(`/api/chats/${sid}`, {method:'DELETE'}); await fetchChatSessions(); if(currentChatId.value===sid) createNewChat(); };
        
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
            const txt = input.value.trim(); if(!txt) return;
            messages.value.push({role:'user',content:txt}); input.value=''; isLoading.value=true; nextTick(() => { const el = document.getElementById('chat-box'); if(el) el.scrollTop = el.scrollHeight; });
            const fd = new FormData(); fd.append('query_text', txt); fd.append('session_id', currentChatId.value);
            try { 
                const r = await fetch('/api/query', {method:'POST', body:fd}); const d = await r.json();
                messages.value.push({role:'assistant', content:d.answer_text}); fetchChatSessions();
                if(d.ticker) { selected3DTicker.value = d.ticker; if(d.answer_text.includes('[TRADINGVIEW_WIDGET]')) nextTick(()=>injectChatWidget(d.ticker)); }
            } catch(e) { messages.value.push({role:'assistant', content:e.message}); } finally { isLoading.value=false; nextTick(() => { const el = document.getElementById('chat-box'); if(el) el.scrollTop = el.scrollHeight; }); }
        };

        /**
         * Inject a TradingView widget placeholder created by assistant
         * responses into the DOM for a given ticker.
         *
         * @param {string} t - Ticker symbol to render in the widget.
         * @returns {void}
         */
        const injectChatWidget = (t) => { document.querySelectorAll('.chat-widget-placeholder:empty').forEach(el => { const id='tv-chat-'+Math.random().toString(36).substring(7); el.id=id; new TradingView.widget({"autosize":true,"symbol":t,"interval":"D","theme":"dark","style":"1","container_id":id}); }); };

        /**
         * Convert markdown text to HTML and replace special widget
         * tokens with placeholder containers.
         *
         * @param {string} t - Raw markdown/text to render.
         * @returns {string} HTML string safe for insertion via `v-html`.
         */
        const renderMarkdown = (t) => { if(!t) return ''; let h=marked.parse(t); if(h.includes('[TRADINGVIEW_WIDGET]')) h=h.replace(/<p>\[TRADINGVIEW_WIDGET\]<\/p>|\[TRADINGVIEW_WIDGET\]/g, '<div class="chat-widget-placeholder" style="width:100%; height:300px; margin-top:10px; border:1px solid #333;"></div>'); return h; };

        /**
         * Refresh the user's favorite tickers from the server.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetchFavorites = async () => { try{ const r=await fetch('/api/favorites'); if(r.ok) favorites.value=await r.json(); }catch(e){} };

        /**
         * Add a new ticker to the user's favorites via the API.
         *
         * @async
         * @returns {Promise<void>}
         */
        const addFavorite = async () => { if(!newFav.value)return; await fetch('/api/favorites',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker:newFav.value.toUpperCase()})}); await fetchFavorites(); newFav.value=''; };

        /**
         * Remove a ticker from the user's favorites and refresh state.
         *
         * @param {string} t - Ticker symbol to remove.
         * @async
         * @returns {Promise<void>}
         */
        const removeFavorite = async (t) => { await fetch(`/api/favorites/${t}`,{method:'DELETE'}); await fetchFavorites(); };

        /**
         * Open the voice input modal; placeholder for voice UX.
         *
         * @returns {void}
         */
        const toggleVoice = () => { showVoice.value = true; };

        return { 
            input, messages, favorites, chatSessions, currentChatId, isLoading, is3DLoaded, 
            showVoice, showFavorites, showSettings, newFav, voiceStatusText, selected3DTicker,
            intelMessages, pizzaData,
            createNewChat, switchChat, deleteChat, sendMessage, renderMarkdown, show3DWindow, 
            fetch3DData, addFavorite, removeFavorite, toggleVoice, toggleWindow 
        };
    }
}).mount('#app');