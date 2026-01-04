/**
 * @module static/app
 *
 * This module bootstraps the Arbitron Systems single-page client application.
 */

const { createApp, ref, onMounted, nextTick, watch } = Vue;

marked.setOptions({ gfm: true, breaks: true });

let maxZIndex = 100;
let offsetCounter = 0;

/**
 * Application setup function for the Vue instance.
 *
 * Initializes reactive state, lifecycle hooks, and helper
 * functions used throughout the single-page application. The
 * returned object exposes reactive properties and methods bound to
 * the Vue template.
 *
 * @returns {Object} Public properties and methods for the Vue app.
 */
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
        
        const renderQueue = ref([]);
        const activeWidgets = new Set();
        let isProcessingQueue = false;

        const showVoice = ref(false);
        const showFavorites = ref(false);
        const showSettings = ref(false);
        const newFav = ref('');
        
        const voiceStatusText = ref('Ready');

        onMounted(async () => {
            await fetchFavorites();
            await fetchChatSessions();
            
            const savedSession = localStorage.getItem('arbitron_last_session');
            if (savedSession) await switchChat(savedSession);
            else createNewChat();

            const win3d = document.getElementById('window-3d');
            if(win3d) {
                makeDraggable(win3d);
                initResizeDetection(win3d);
                attachWindowResizer(win3d);
                win3d.onmousedown = () => bringToFront(win3d);
            }

            makeResizable();
        });

        /**
         * Detects when user interacts with the CSS resize handle
         * and toggles a class for visual/functional feedback.
         */
        const initResizeDetection = (el) => {
            el.addEventListener('mousedown', (e) => {
                const rect = el.getBoundingClientRect();
                const resizerSize = 25; 
                const isRightEdge = e.clientX > rect.right - resizerSize;
                const isBottomEdge = e.clientY > rect.bottom - resizerSize;

                if (isRightEdge && isBottomEdge) {
                    el.classList.add('is-resizing');
                    const stopResize = () => {
                        el.classList.remove('is-resizing');
                        window.removeEventListener('mouseup', stopResize);
                    };
                    window.addEventListener('mouseup', stopResize);
                }
            });
        };

        /**
         * Enable resizing of the chat panel by dragging the resizer.
         *
         * Attaches mouse listeners to implement a column resize and
         * constrains the width to sensible bounds for usability.
         *
         * @returns {void}
         */
        const makeResizable = () => {
            const resizer = document.getElementById('resizer');
            const sidebar = document.getElementById('chat-panel');
            if (!resizer || !sidebar) return;
            resizer.addEventListener('mousedown', function(e) {
                e.preventDefault();
                document.addEventListener('mousemove', resize);
                document.addEventListener('mouseup', stopResize);
            });
            function resize(e) {
                const newWidth = e.clientX - 50; 
                if (newWidth > 200 && newWidth < 800) { sidebar.style.width = newWidth + 'px'; }
            }
            function stopResize() {
                document.removeEventListener('mousemove', resize);
                document.removeEventListener('mouseup', stopResize);
            }
        };

        /**
         * Show the 3D quant window and bring it to the front.
         *
         * @returns {void}
         */
        const show3DWindow = () => {
            const win = document.getElementById('window-3d');
            if(win) { win.style.display = 'flex'; bringToFront(win); }
        };

        /**
         * Fetch and render the 3D volatility surface for the
         * currently-selected ticker using the server API and Plotly.
         *
         * @async
         * @returns {Promise<void>} Resolves when the Plotly chart is rendered.
         */
        const fetch3DData = async () => {
            const r = await fetch(`/api/quant/surface?ticker=${selected3DTicker.value}`);
            const fig = await r.json();
            Plotly.newPlot('quant-chart', fig.data, fig.layout, { responsive: true, displayModeBar: false });
            is3DLoaded.value = true;
        };

        watch(selected3DTicker, () => { if (is3DLoaded.value) fetch3DData(); });

        /**
         * Make an element draggable using its `.chart-title-bar` child
         * as the drag handle. Updates element `top`/`left` styles on
         * pointer movement and toggles a dragging CSS class.
         *
         * @param {HTMLElement} elmnt - The root element to make draggable.
         * @returns {void}
         */
        const makeDraggable = (elmnt) => {
            let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
            const header = elmnt.querySelector('.chart-title-bar');
            if (header) header.onmousedown = dragMouseDown;
            function dragMouseDown(e) {
                if (e.target.closest('.chart-remove-btn') || e.target.closest('select')) return;
                e.preventDefault(); pos3 = e.clientX; pos4 = e.clientY;
                elmnt.classList.add('is-dragging'); document.body.classList.add('window-dragging'); bringToFront(elmnt);
                document.onmouseup = closeDragElement; document.onmousemove = elementDrag;
            }
            function elementDrag(e) {
                e.preventDefault(); pos1 = pos3 - e.clientX; pos2 = pos4 - e.clientY;
                pos3 = e.clientX; pos4 = e.clientY;
                elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
                elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
            }
            function closeDragElement() {
                document.onmouseup = null; document.onmousemove = null;
                elmnt.classList.remove('is-dragging'); document.body.classList.remove('window-dragging');
            }
        };

        /**
         * Attach a visible top-layer resize handle to a window and
         * implement mouse-based resizing so the handle remains accessible
         * even when the inner app covers the window edges.
         */
        const attachWindowResizer = (el) => {
            if (!el) return;
            // avoid adding twice
            if (el.querySelector('.window-resize-handle')) return;
            const handle = document.createElement('div');
            handle.className = 'window-resize-handle';
            el.appendChild(handle);

            let startX = 0, startY = 0, startW = 0, startH = 0;

            const onMouseDown = (e) => {
                e.stopPropagation(); e.preventDefault();
                el.classList.add('is-resizing');
                startX = e.clientX; startY = e.clientY;
                startW = el.offsetWidth; startH = el.offsetHeight;
                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp, { once: true });
            };
            const onMouseMove = (e) => {
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                el.style.width = Math.max(200, startW + dx) + 'px';
                el.style.height = Math.max(150, startH + dy) + 'px';
            };
            const onMouseUp = (e) => {
                el.classList.remove('is-resizing');
                document.removeEventListener('mousemove', onMouseMove);
            };

            handle.addEventListener('mousedown', onMouseDown);
        };

        /**
         * Increase the global z-index and mark the given element as
         * the active window so it appears above others.
         *
         * @param {HTMLElement} el - Element to bring forward.
         * @returns {void}
         */
        const bringToFront = (el) => {
            maxZIndex++; el.style.zIndex = maxZIndex;
            document.querySelectorAll('.chart-card').forEach(c => c.classList.remove('active-window'));
            el.classList.add('active-window');
        };

        watch(favorites, (newVal, oldVal) => {
            newVal.forEach(t => { if (!activeWidgets.has(t)) renderQueue.value.push(t); });
            if (oldVal) oldVal.forEach(t => { if (!newVal.includes(t)) removeWidgetFromDOM(t); });
            processQueue();
        }, { deep: true });

        /**
         * Sequentially process the widget render queue to avoid layout churn.
         *
         * Widgets are created one at a time with a small delay between
         * insertions; this function is re-entrant-safe and returns when
         * the queue is empty.
         *
         * @async
         * @returns {Promise<void>}
         */
        const processQueue = async () => {
            if (isProcessingQueue || renderQueue.value.length === 0) return;
            isProcessingQueue = true;
            const ticker = renderQueue.value.shift();
            createWidgetDOM(ticker);
            activeWidgets.add(ticker);
            setTimeout(() => { isProcessingQueue = false; processQueue(); }, 300); 
        };

        /**
         * Create and insert a TradingView widget card for a given ticker.
         *
         * This function creates DOM nodes, initializes TradingView,
         * attaches drag behavior, and registers removal handlers. If a
         * widget for the ticker already exists the call is a no-op.
         *
         * @param {string} ticker - The ticker symbol to render.
         * @returns {void}
         */
        const createWidgetDOM = (ticker) => {
            const container = document.getElementById('desktop-area');
            if (!container || document.getElementById(`card-${ticker}`)) return;

            const div = document.createElement('div');
            div.className = 'chart-card';
            div.id = `card-${ticker}`;
            offsetCounter++; if (offsetCounter > 10) offsetCounter = 0;
            div.style.top = (50 + offsetCounter * 30) + 'px';
            div.style.left = (50 + offsetCounter * 30) + 'px';
            
            const widgetId = `tv-${ticker}-${Math.random().toString(36).substr(2, 5)}`;
            div.innerHTML = `
                <div class="chart-title-bar">
                    <span>${ticker}</span>
                    <span class="chart-remove-btn">
                        <svg class="del-icon-svg" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </span>
                </div>
                <div id="${widgetId}" class="tv-widget-container"></div>
            `;
            container.appendChild(div);
            makeDraggable(div);
            initResizeDetection(div);
            attachWindowResizer(div);
            div.onmousedown = () => bringToFront(div);
            div.querySelector('.chart-remove-btn').onclick = () => removeFavorite(ticker);
            new TradingView.widget({"autosize": true, "symbol": ticker, "interval": "D", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_top_toolbar": true, "hide_legend": true, "container_id": widgetId});
            bringToFront(div);
        };

        /**
         * Remove a widget DOM node for the specified ticker and update
         * internal state.
         *
         * @param {string} ticker - The ticker symbol whose widget should be removed.
         * @returns {void}
         */
        const removeWidgetFromDOM = (ticker) => {
            const el = document.getElementById(`card-${ticker}`);
            if (el) el.remove();
            activeWidgets.delete(ticker);
        };

        /**
         * Fetch list of chat sessions from the server and update state.
         *
         * @async
         * @returns {Promise<void>} Resolves after `chatSessions` is updated.
         */
        const fetchChatSessions = async () => { try { const r = await fetch('/api/chats'); if (r.ok) chatSessions.value = await r.json(); } catch (e) {} };

        /**
         * Create a new local chat session identifier and persist it to storage.
         *
         * @async
         * @returns {Promise<void>}
         */
        const createNewChat = async () => { const newId = 'session_' + Date.now().toString().slice(-4); currentChatId.value = newId; messages.value = []; localStorage.setItem('arbitron_last_session', newId); await fetchChatSessions(); };

        /**
         * Switch the UI to an existing chat session and load its messages.
         *
         * @param {string} sid - Session identifier to switch to.
         * @async
         * @returns {Promise<void>}
         */
        const switchChat = async (sid) => { currentChatId.value = sid; localStorage.setItem('arbitron_last_session', sid); isLoading.value = true; try { const r = await fetch(`/api/chats/${sid}/messages`); if(r.ok) messages.value = await r.json(); else createNewChat(); } catch(e){} finally { isLoading.value = false; } };

        /**
         * Delete a chat session after user confirmation, and refresh sessions.
         *
         * @param {string} sid - Session identifier to delete.
         * @async
         * @returns {Promise<void>}
         */
        const deleteChat = async (sid) => { if(!confirm("Delete?")) return; await fetch(`/api/chats/${sid}`, {method:'DELETE'}); await fetchChatSessions(); if(currentChatId.value===sid) createNewChat(); };
        
        /**
         * Send the current input text to the server and append the
         * assistant's reply to the local message list.
         *
         * The function provides optimistic UI updates, posts form data
         * to `/api/query`, and handles attaching TradingView widgets
         * signaled by the assistant response.
         *
         * @async
         * @returns {Promise<void>}
         */
        const sendMessage = async () => {
            const txt = input.value.trim(); if(!txt) return;
            messages.value.push({role:'user',content:txt}); input.value=''; isLoading.value=true; nextTick(() => { const el = document.getElementById('chat-box'); if(el) el.scrollTop = el.scrollHeight; });
            const fd = new FormData(); fd.append('query_text', txt); fd.append('session_id', currentChatId.value);
            try { const r = await fetch('/api/query', {method:'POST', body:fd}); const d = await r.json();
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
         * Render markdown to HTML and replace special widget tokens
         * with placeholder containers.
         *
         * @param {string} t - Raw markdown/text to render.
         * @returns {string} HTML string safe for insertion via v-html.
         */
        const renderMarkdown = (t) => { if(!t) return ''; let h=marked.parse(t); if(h.includes('[TRADINGVIEW_WIDGET]')) h=h.replace(/<p>\[TRADINGVIEW_WIDGET\]<\/p>|\[TRADINGVIEW_WIDGET\]/g, '<div class="chat-widget-placeholder" style="width:100%; height:300px; margin-top:10px; border:1px solid #333;"></div>'); return h; };

        /**
         * Fetch persisted favorites from the server and update client state.
         *
         * @async
         * @returns {Promise<void>}
         */
        const fetchFavorites = async () => { try{ const r=await fetch('/api/favorites'); if(r.ok) favorites.value=await r.json(); }catch(e){} };

        /**
         * Add a new favorite ticker via the server API and refresh state.
         *
         * @async
         * @returns {Promise<void>}
         */
        const addFavorite = async () => { if(!newFav.value)return; await fetch('/api/favorites',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker:newFav.value.toUpperCase()})}); await fetchFavorites(); newFav.value=''; };

        /**
         * Remove a ticker from the user's favorites via the server API.
         *
         * @param {string} t - Ticker symbol to remove.
         * @async
         * @returns {Promise<void>}
         */
        const removeFavorite = async (t) => { await fetch(`/api/favorites/${t}`,{method:'DELETE'}); await fetchFavorites(); };

        /**
         * Open the voice input modal. Placeholder for voice UX.
         *
         * @returns {void}
         */
        const toggleVoice = () => { showVoice.value = true; };

        /**
         * Toggle listening state for voice input. Implementation is a
         * placeholder and should be extended for production.
         *
         * @returns {void}
         */
        const toggleListening = () => {};

        return { input, messages, favorites, chatSessions, currentChatId, isLoading, is3DLoaded, showVoice, showFavorites, showSettings, newFav, voiceStatusText, selected3DTicker, createNewChat, switchChat, deleteChat, sendMessage, renderMarkdown, show3DWindow, fetch3DData, addFavorite, removeFavorite, toggleVoice, toggleListening };
    }
}).mount('#app');