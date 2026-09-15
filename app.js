(() => {
    "use strict";

    const tg = window.Telegram?.WebApp;

    if (tg) {
        tg.ready();
        tg.expand();
        tg.enableClosingConfirmation?.();
    }

    const API_BASE = window.location.origin;

    const state = {
        symbol: "BTC/USDT",
        timeframe: "15m",
        candles: [],
        analysis: null,
        loading: false,
        chart: null
    };

    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => [...document.querySelectorAll(selector)];

    function telegramInitData() {
        return tg?.initData || "";
    }

    function apiHeaders() {
        const headers = {
            "Content-Type": "application/json"
        };

        const initData = telegramInitData();

        if (initData) {
            headers["X-Telegram-Init-Data"] = initData;
        }

        return headers;
    }

    async function api(url, options = {}) {
        const response = await fetch(`${API_BASE}${url}`, {
            ...options,
            headers: {
                ...apiHeaders(),
                ...(options.headers || {})
            }
        });

        let data = null;

        try {
            data = await response.json();
        } catch {
            throw new Error(`Сервер вернул некорректный ответ (${response.status})`);
        }

        if (!response.ok) {
            throw new Error(data?.error || data?.message || `Ошибка сервера: ${response.status}`);
        }

        return data;
    }

    function setText(selector, value) {
        const element = $(selector);
        if (element) element.textContent = value ?? "—";
    }

    function formatNumber(value, digits = 4) {
        const number = Number(value);

        if (!Number.isFinite(number)) {
            return "—";
        }

        if (Math.abs(number) >= 1000) {
            return number.toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        return number.toLocaleString("en-US", {
            minimumFractionDigits: 0,
            maximumFractionDigits: digits
        });
    }

    function normalizeSymbol(symbol) {
        return String(symbol || "BTC/USDT")
            .replace("-", "/")
            .replace("_", "/")
            .toUpperCase();
    }

    function timeframeLabel(tf) {
        const labels = {
            "1m": "1 МИН",
            "5m": "5 МИН",
            "15m": "15 МИН",
            "1h": "1 ЧАС",
            "4h": "4 ЧАСА",
            "1d": "1 ДЕНЬ",
            "1w": "1 НЕДЕЛЯ"
        };

        return labels[tf] || String(tf).toUpperCase();
    }

    function setLoading(value) {
        state.loading = value;

        $$(".analyze-button, [data-action='analyze']").forEach(button => {
            button.disabled = value;
            button.classList.toggle("loading", value);

            if (value) {
                button.dataset.oldText = button.textContent;
                button.textContent = "АНАЛИЗ...";
            } else if (button.dataset.oldText) {
                button.textContent = button.dataset.oldText;
            }
        });

        const loader = $(".loader");
        if (loader) loader.classList.toggle("visible", value);
    }

    function showError(message) {
        const error = $(".error-message");

        if (error) {
            error.textContent = message;
            error.classList.add("visible");

            setTimeout(() => {
                error.classList.remove("visible");
            }, 6000);

            return;
        }

        console.error(message);
    }

    function setActive(selector, value, attribute) {
        $$(selector).forEach(element => {
            element.classList.toggle(
                "active",
                element.getAttribute(attribute) === value
            );
        });
    }

    function setupTimeframes() {
        $$("[data-timeframe]").forEach(button => {
            button.addEventListener("click", () => {
                state.timeframe = button.dataset.timeframe;

                setActive(
                    "[data-timeframe]",
                    state.timeframe,
                    "data-timeframe"
                );

                loadMarket();
            });
        });
    }

    function setupSymbols() {
        $$("[data-symbol]").forEach(button => {
            button.addEventListener("click", () => {
                state.symbol = normalizeSymbol(button.dataset.symbol);

                setActive(
                    "[data-symbol]",
                    state.symbol,
                    "data-symbol"
                );

                loadMarket();
            });
        });
    }

    function setupAnalyzeButtons() {
        $$("[data-action='analyze'], .analyze-button").forEach(button => {
            button.addEventListener("click", runAnalysis);
        });
    }

    function setupBackButtons() {
        $$("[data-action='back']").forEach(button => {
            button.addEventListener("click", () => {
                if (tg) {
                    tg.close();
                } else {
                    history.back();
                }
            });
        });
    }

    async function loadMarket() {
        try {
            const symbol = encodeURIComponent(state.symbol);
            const timeframe = encodeURIComponent(state.timeframe);

            const data = await api(
                `/api/candles?symbol=${symbol}&timeframe=${timeframe}`
            );

            state.candles = Array.isArray(data.candles)
                ? data.candles
                : [];

            updateMarketHeader(data);
            drawChart();
        } catch (error) {
            console.error(error);
            showError(error.message || "Не удалось получить рыночные данные");
        }
    }

    function updateMarketHeader(data = {}) {
        setText(".symbol-name", normalizeSymbol(data.symbol || state.symbol));
        setText(".timeframe-name", timeframeLabel(data.timeframe || state.timeframe));

        const candles = data.candles || state.candles;

        if (candles.length) {
            const last = candles[candles.length - 1];

            setText(
                ".current-price",
                formatNumber(last.close, 8)
            );

            if (last.timestamp) {
                setText(
                    ".market-time",
                    new Date(Number(last.timestamp)).toLocaleString("ru-RU")
                );
            }
        }
    }

    function candleValue(candle, key, index) {
        const value = candle?.[key];

        if (value !== undefined && value !== null) {
            return Number(value);
        }

        if (Array.isArray(candle)) {
            const positions = {
                timestamp: 0,
                open: 1,
                high: 2,
                low: 3,
                close: 4,
                volume: 5
            };

            return Number(candle[positions[key]]);
        }

        return index;
    }

    function normalizeCandles(candles) {
        return candles
            .map((candle, index) => ({
                timestamp: candleValue(candle, "timestamp", index),
                open: candleValue(candle, "open", index),
                high: candleValue(candle, "high", index),
                low: candleValue(candle, "low", index),
                close: candleValue(candle, "close", index),
                volume: candleValue(candle, "volume", index)
            }))
            .filter(c =>
                Number.isFinite(c.open) &&
                Number.isFinite(c.high) &&
                Number.isFinite(c.low) &&
                Number.isFinite(c.close)
            );
    }

    function getCanvas() {
        return (
            $("#chart") ||
            $("#chartCanvas") ||
            $(".chart-canvas") ||
            document.querySelector("canvas")
        );
    }

    function drawChart() {
        const canvas = getCanvas();

        if (!canvas) {
            return;
        }

        const candles = normalizeCandles(state.candles);

        if (!candles.length) {
            return;
        }

        const ctx = canvas.getContext("2d");

        const rect = canvas.getBoundingClientRect();

        const width = Math.max(
            300,
            Math.floor(rect.width || canvas.clientWidth || 700)
        );

        const height = Math.max(
            280,
            Math.floor(rect.height || canvas.clientHeight || 420)
        );

        const dpr = Math.min(window.devicePixelRatio || 1, 2);

        canvas.width = width * dpr;
        canvas.height = height * dpr;

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        ctx.clearRect(0, 0, width, height);

        const visible = candles.slice(-100);

        const padding = {
            top: 25,
            right: 55,
            bottom: 35,
            left: 10
        };

        const chartWidth =
            width - padding.left - padding.right;

        const chartHeight =
            height - padding.top - padding.bottom;

        const highs = visible.map(c => c.high);
        const lows = visible.map(c => c.low);

        let maxPrice = Math.max(...highs);
        let minPrice = Math.min(...lows);

        const range = Math.max(maxPrice - minPrice, 0.00000001);
        const margin = range * 0.08;

        maxPrice += margin;
        minPrice -= margin;

        const priceRange = maxPrice - minPrice;

        function y(price) {
            return (
                padding.top +
                ((maxPrice - price) / priceRange) * chartHeight
            );
        }

        const candleWidth =
            chartWidth / visible.length;

        // Background
        ctx.fillStyle = "#050505";
        ctx.fillRect(0, 0, width, height);

        // Grid
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(255,255,255,0.055)";

        for (let i = 0; i <= 5; i++) {
            const gy =
                padding.top +
                (chartHeight / 5) * i;

            ctx.beginPath();
            ctx.moveTo(padding.left, gy);
            ctx.lineTo(width - padding.right, gy);
            ctx.stroke();

            const price =
                maxPrice -
                (priceRange / 5) * i;

            ctx.fillStyle = "rgba(255,255,255,0.55)";
            ctx.font = "10px Arial";
            ctx.textAlign = "left";
            ctx.fillText(
                formatNumber(price, 6),
                width - padding.right + 8,
                gy + 4
            );
        }

        // Candles
        visible.forEach((candle, index) => {
            const x =
                padding.left +
                index * candleWidth +
                candleWidth / 2;

            const openY = y(candle.open);
            const closeY = y(candle.close);
            const highY = y(candle.high);
            const lowY = y(candle.low);

            const bullish = candle.close >= candle.open;

            ctx.strokeStyle = "#ffffff";
            ctx.fillStyle = bullish ? "#ffffff" : "#111111";

            // Wick
            ctx.lineWidth = Math.max(1, candleWidth * 0.07);

            ctx.beginPath();
            ctx.moveTo(x, highY);
            ctx.lineTo(x, lowY);
            ctx.stroke();

            // Body
            const bodyWidth =
                Math.max(
                    2,
                    Math.min(14, candleWidth * 0.62)
                );

            const bodyTop =
                Math.min(openY, closeY);

            const bodyHeight =
                Math.max(
                    1,
                    Math.abs(closeY - openY)
                );

            ctx.fillRect(
                x - bodyWidth / 2,
                bodyTop,
                bodyWidth,
                bodyHeight
            );

            if (!bullish) {
                ctx.strokeStyle = "#ffffff";
                ctx.strokeRect(
                    x - bodyWidth / 2,
                    bodyTop,
                    bodyWidth,
                    bodyHeight
                );
            }
        });

        // Last price line
        const last = visible[visible.length - 1];

        if (last) {
            const lastY = y(last.close);

            ctx.strokeStyle = "rgba(255,255,255,0.75)";
            ctx.setLineDash([4, 4]);

            ctx.beginPath();
            ctx.moveTo(padding.left, lastY);
            ctx.lineTo(width - padding.right, lastY);
            ctx.stroke();

            ctx.setLineDash([]);

            ctx.fillStyle = "#ffffff";
            ctx.fillRect(
                width - padding.right,
                lastY - 10,
                padding.right,
                20
            );

            ctx.fillStyle = "#000000";
            ctx.font = "bold 10px Arial";
            ctx.textAlign = "center";

            ctx.fillText(
                formatNumber(last.close, 6),
                width - padding.right / 2,
                lastY + 4
            );
        }

        // Time labels
        ctx.fillStyle = "rgba(255,255,255,0.38)";
        ctx.font = "9px Arial";
        ctx.textAlign = "center";

        const labelCount = Math.min(5, visible.length);

        for (let i = 0; i < labelCount; i++) {
            const index = Math.floor(
                (visible.length - 1) *
                (i / Math.max(1, labelCount - 1))
            );

            const candle = visible[index];

            if (!candle.timestamp) continue;

            const x =
                padding.left +
                index * candleWidth +
                candleWidth / 2;

            const date = new Date(Number(candle.timestamp));

            ctx.fillText(
                date.toLocaleTimeString("ru-RU", {
                    hour: "2-digit",
                    minute: "2-digit"
                }),
                x,
                height - 10
            );
        }

        state.chart = {
            canvas,
            ctx,
            candles: visible,
            minPrice,
            maxPrice,
            padding,
            chartWidth,
            chartHeight
        };
    }

    function getAnalysisText(analysis) {
        if (!analysis) {
            return "Анализ пока не выполнен.";
        }

        const fields = [
            analysis.reason,
            analysis.summary,
            analysis.explanation,
            analysis.market_state,
            analysis.marketState
        ];

        for (const value of fields) {
            if (typeof value === "string" && value.trim()) {
                return value;
            }
        }

        return "Анализ выполнен. Проверь направление и уровни ниже.";
    }

    function findBias(analysis) {
        const value =
            analysis?.bias ||
            analysis?.direction ||
            analysis?.signal ||
            analysis?.setup ||
            "";

        const text = String(value).toUpperCase();

        if (text.includes("LONG") || text.includes("ЛОНГ")) {
            return "LONG";
        }

        if (text.includes("SHORT") || text.includes("ШОРТ")) {
            return "SHORT";
        }

        return "WAIT";
    }

    function findConfidence(analysis) {
        const values = [
            analysis?.confidence_score,
            analysis?.confidence,
            analysis?.confidenceScore
        ];

        for (const value of values) {
            const number = Number(value);

            if (Number.isFinite(number)) {
                return number <= 1
                    ? Math.round(number * 100)
                    : Math.round(number);
            }
        }

        return null;
    }

    function extractNumber(value) {
        if (value === null || value === undefined) {
            return null;
        }

        if (typeof value === "number") {
            return Number.isFinite(value) ? value : null;
        }

        const match = String(value)
            .replace(",", ".")
            .match(/-?\d+(?:\.\d+)?/);

        return match ? Number(match[0]) : null;
    }

    function getLevel(analysis, names) {
        for (const name of names) {
            if (
                analysis &&
                analysis[name] !== undefined &&
                analysis[name] !== null
            ) {
                const number = extractNumber(analysis[name]);

                if (number !== null) {
                    return number;
                }
            }
        }

        return null;
    }

    function updateAnalysisUI(analysis) {
        state.analysis = analysis;

        const bias = findBias(analysis);
        const confidence = findConfidence(analysis);

        setText(".bias-value", bias);

        const biasElement =
            $(".bias-value") ||
            $(".signal-value");

        if (biasElement) {
            biasElement.classList.remove(
                "long",
                "short",
                "wait"
            );

            biasElement.classList.add(
                bias.toLowerCase()
            );
        }

        if (confidence !== null) {
            setText(
                ".confidence-value",
                `${confidence}%`
            );
        }

        const entry = getLevel(
            analysis,
            [
                "entry",
                "entry_price",
                "entryPrice",
                "entry_zone"
            ]
        );

        const stop = getLevel(
            analysis,
            [
                "stop",
                "stop_loss",
                "stopLoss",
                "invalidation"
            ]
        );

        const tp1 = getLevel(
            analysis,
            ["tp1", "target1", "target_1"]
        );

        const tp2 = getLevel(
            analysis,
            ["tp2", "target2", "target_2"]
        );

        const tp3 = getLevel(
            analysis,
            ["tp3", "target3", "target_3"]
        );

        setText(".entry-value", entry !== null ? formatNumber(entry, 8) : "—");
        setText(".stop-value", stop !== null ? formatNumber(stop, 8) : "—");
        setText(".tp1-value", tp1 !== null ? formatNumber(tp1, 8) : "—");
        setText(".tp2-value", tp2 !== null ? formatNumber(tp2, 8) : "—");
        setText(".tp3-value", tp3 !== null ? formatNumber(tp3, 8) : "—");

        const chat = $(".ai-response");

        if (chat) {
            chat.textContent = getAnalysisText(analysis);
        }

        const signalText = $(".signal-text");

        if (signalText) {
            if (bias === "LONG") {
                signalText.textContent = "Условия больше склоняются к LONG.";
            } else if (bias === "SHORT") {
                signalText.textContent = "Условия больше склоняются к SHORT.";
            } else {
                signalText.textContent = "Чёткого подтверждённого входа пока нет.";
            }
        }

        updateAdditionalFields(analysis);
        drawChartWithLevels();
    }

    function updateAdditionalFields(analysis) {
        const mappings = {
            ".market-state": [
                "market_state",
                "marketState",
                "state"
            ],
            ".structure-value": [
                "structure",
                "market_structure"
            ],
            ".pattern-value": [
                "chart_patterns",
                "patterns",
                "pattern"
            ],
            ".candles-value": [
                "candle_patterns",
                "candles"
            ],
            ".liquidity-value": [
                "liquidity"
            ],
            ".volume-value": [
                "volume"
            ],
            ".indicators-value": [
                "indicators"
            ],
            ".derivatives-value": [
                "derivatives"
            ]
        };

        Object.entries(mappings).forEach(
            ([selector, keys]) => {
                const element = $(selector);

                if (!element) return;

                for (const key of keys) {
                    const value = analysis?.[key];

                    if (
                        value !== undefined &&
                        value !== null
                    ) {
                        if (typeof value === "object") {
                            element.textContent =
                                JSON.stringify(value);
                        } else {
                            element.textContent =
                                String(value);
                        }

                        break;
                    }
                }
            }
        );
    }

    function drawChartWithLevels() {
        drawChart();

        if (!state.chart || !state.analysis) {
            return;
        }

        const {
            canvas,
            ctx,
            padding,
            chartWidth,
            chartHeight,
            minPrice,
            maxPrice
        } = state.chart;

        const analysis = state.analysis;

        function priceToY(price) {
            return (
                padding.top +
                ((maxPrice - price) /
                    (maxPrice - minPrice)) *
                    chartHeight
            );
        }

        const levels = [
            {
                names: ["entry", "entry_price", "entryPrice"],
                label: "ENTRY"
            },
            {
                names: ["stop", "stop_loss", "stopLoss", "invalidation"],
                label: "STOP"
            },
            {
                names: ["tp1", "target1", "target_1"],
                label: "TP1"
            },
            {
                names: ["tp2", "target2", "target_2"],
                label: "TP2"
            },
            {
                names: ["tp3", "target3", "target_3"],
                label: "TP3"
            }
        ];

        levels.forEach(level => {
            const price = getLevel(
                analysis,
                level.names
            );

            if (price === null) {
                return;
            }

            if (
                price < minPrice ||
                price > maxPrice
            ) {
                return;
            }

            const y = priceToY(price);

            ctx.save();

            ctx.strokeStyle =
                level.label === "STOP"
                    ? "rgba(255,255,255,0.35)"
                    : "rgba(255,255,255,0.8)";

            ctx.lineWidth = 1;
            ctx.setLineDash([5, 4]);

            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(
                canvas.clientWidth - padding.right,
                y
            );
            ctx.stroke();

            ctx.setLineDash([]);

            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 9px Arial";
            ctx.textAlign = "left";

            ctx.fillText(
                `${level.label} ${formatNumber(price, 6)}`,
                padding.left + 5,
                y - 5
            );

            ctx.restore();
        });
    }

    async function runAnalysis() {
        if (state.loading) {
            return;
        }

        setLoading(true);

        try {
            const data = await api("/api/analyze", {
                method: "POST",
                body: JSON.stringify({
                    symbol: state.symbol,
                    timeframe: state.timeframe
                })
            });

            const analysis =
                data.analysis ||
                data.result ||
                data;

            if (Array.isArray(data.candles)) {
                state.candles = data.candles;
            }

            updateMarketHeader(data);
            updateAnalysisUI(analysis);

            addChatMessage(
                "AI",
                buildSignalMessage(analysis)
            );

            if (tg?.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred(
                    "success"
                );
            }
        } catch (error) {
            console.error(error);

            showError(
                error.message ||
                "Не удалось выполнить анализ"
            );

            if (tg?.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred(
                    "error"
                );
            }
        } finally {
            setLoading(false);
        }
    }

    function buildSignalMessage(analysis) {
        const bias = findBias(analysis);
        const confidence = findConfidence(analysis);

        if (bias === "LONG") {
            return `Сигнал: LONG${confidence !== null ? ` | Уверенность: ${confidence}%` : ""}. Это условительный сценарий, а не гарантия движения.`;
        }

        if (bias === "SHORT") {
            return `Сигнал: SHORT${confidence !== null ? ` | Уверенность: ${confidence}%` : ""}. Это условительный сценарий, а не гарантия движения.`;
        }

        return "Сигнал: ОЖИДАНИЕ. Подтверждённого входа недостаточно.";
    }

    function addChatMessage(author, text) {
        const container =
            $(".chat-messages") ||
            $(".ai-chat");

        if (!container) {
            return;
        }

        const message = document.createElement("div");

        message.className =
            author === "AI"
                ? "chat-message ai"
                : "chat-message user";

        message.textContent = text;

        container.appendChild(message);

        container.scrollTop =
            container.scrollHeight;
    }

    function setupChat() {
        const input =
            $(".chat-input") ||
            $("input[name='message']") ||
            $("#chatInput");

        const send =
            $(".chat-send") ||
            $("[data-action='send-chat']");

        if (!input || !send) {
            return;
        }

        async function sendMessage() {
            const text = input.value.trim();

            if (!text) {
                return;
            }

            addChatMessage("USER", text);

            input.value = "";

            try {
                const data = await api("/api/chat", {
                    method: "POST",
                    body: JSON.stringify({
                        symbol: state.symbol,
                        timeframe: state.timeframe,
                        message: text,
                        analysis: state.analysis
                    })
                });

                const answer =
                    data.answer ||
                    data.message ||
                    data.response ||
                    "Нет ответа.";

                addChatMessage(
                    "AI",
                    answer
                );
            } catch (error) {
                addChatMessage(
                    "AI",
                    `Ошибка: ${error.message}`
                );
            }
        }

        send.addEventListener(
            "click",
            sendMessage
        );

        input.addEventListener(
            "keydown",
            event => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    sendMessage();
                }
            }
        );
    }

    function setupResize() {
        let timeout;

        window.addEventListener(
            "resize",
            () => {
                clearTimeout(timeout);

                timeout = setTimeout(() => {
                    if (state.analysis) {
                        drawChartWithLevels();
                    } else {
                        drawChart();
                    }
                }, 100);
            }
        );
    }

    function setupTouchHaptics() {
        document.addEventListener(
            "click",
            event => {
                const button =
                    event.target.closest("button");

                if (!button || !tg?.HapticFeedback) {
                    return;
                }

                tg.HapticFeedback.impactOccurred(
                    "light"
                );
            }
        );
    }

    function applyTelegramTheme() {
        if (!tg) {
            return;
        }

        document.documentElement.style.setProperty(
            "--tg-bg",
            tg.backgroundColor || "#000000"
        );

        document.documentElement.style.setProperty(
            "--tg-text",
            tg.themeParams?.text_color || "#ffffff"
        );
    }

    function exposeGlobalAPI() {
        window.NEZZX = {
            state,
            analyze: runAnalysis,
            loadMarket,
            drawChart
        };
    }

    async function init() {
        applyTelegramTheme();

        setupTimeframes();
        setupSymbols();
        setupAnalyzeButtons();
        setupBackButtons();
        setupChat();
        setupResize();
        setupTouchHaptics();
        exposeGlobalAPI();

        setActive(
            "[data-timeframe]",
            state.timeframe,
            "data-timeframe"
        );

        setActive(
            "[data-symbol]",
            state.symbol,
            "data-symbol"
        );

        await loadMarket();
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            init
        );
    } else {
        init();
    }
})();