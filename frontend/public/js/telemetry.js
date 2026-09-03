/* =========================================================
   TICKETGENIE - FRONTEND DISTRIBUTED TELEMETRY & TRACING
   ========================================================= */

(function () {
  if (window.TicketGenieTelemetry) return;

  function generateHex(length) {
    let result = "";
    const characters = "0123456789abcdef";
    for (let i = 0; i < length; i++) {
      result += characters.charAt(Math.floor(Math.random() * characters.length));
    }
    return result;
  }

  function generateW3CTraceParent() {
    const traceId = generateHex(32);
    const spanId = generateHex(16);
    return `00-${traceId}-${spanId}-01`;
  }

  const Telemetry = {
    appInsights: null,
    initialized: false,

    getTraceHeaders() {
      return {
        "traceparent": generateW3CTraceParent(),
        "tracestate": "ticketgenie=frontend"
      };
    },

    async init() {
      if (this.initialized) return;

      // Install fetch interceptor for immediate W3C trace header propagation
      this.patchFetch();

      try {
        const response = await fetch("/api/config").catch(() => null);
        let connectionString = "";

        if (response && response.ok) {
          const config = await response.json().catch(() => ({}));
          connectionString = config.appInsightsConnectionString || "";
        }

        if (!connectionString) {
          return;
        }

        if (!window.Microsoft || !window.Microsoft.ApplicationInsights) {
          await this.loadSdkScript();
        }

        if (window.Microsoft && window.Microsoft.ApplicationInsights) {
          const snippet = new window.Microsoft.ApplicationInsights.ApplicationInsights({
            config: {
              connectionString: connectionString,
              enableCorsCorrelation: true,
              distributedTracingMode: 2, // W3C Distributed Tracing Mode
              enableAutoRouteTracking: true,
              enableUnhandledPromiseRejectionTracking: true,
              disableFetchTracking: false,
              disableAjaxTracking: false
            }
          });

          snippet.loadAppInsights();
          snippet.trackPageView({ name: document.title || window.location.pathname });

          this.appInsights = snippet;
          this.initialized = true;
          console.log("[Telemetry] Azure Application Insights client telemetry & W3C distributed tracing initialized.");
        }
      } catch (err) {
        console.warn("[Telemetry] Initialization failed:", err);
      }
    },

    patchFetch() {
      if (window._fetchPatched) return;
      const originalFetch = window.fetch;

      window.fetch = function (resource, options = {}) {
        const url = typeof resource === "string" ? resource : resource?.url || "";
        
        // Only inject traceparent headers into backend API requests
        if (url.includes("/api/")) {
          options = options || {};
          let headers = options.headers || {};

          if (headers instanceof Headers) {
            if (!headers.has("traceparent")) {
              headers.set("traceparent", generateW3CTraceParent());
            }
          } else if (Array.isArray(headers)) {
            const hasTrace = headers.some(([k]) => k.toLowerCase() === "traceparent");
            if (!hasTrace) {
              headers.push(["traceparent", generateW3CTraceParent()]);
            }
          } else {
            const hasTrace = Object.keys(headers).some((k) => k.toLowerCase() === "traceparent");
            if (!hasTrace) {
              headers = {
                ...headers,
                "traceparent": generateW3CTraceParent()
              };
            }
          }
          options.headers = headers;
        }

        return originalFetch.call(this, resource, options);
      };

      window._fetchPatched = true;
    },

    loadSdkScript() {
      return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://js.monitor.azure.com/scripts/b/ai.2.min.js";
        script.async = true;
        script.onload = () => resolve();
        script.onerror = (err) => reject(err);
        document.head.appendChild(script);
      });
    },

    trackEvent(name, properties = {}) {
      if (this.appInsights) {
        this.appInsights.trackEvent({ name }, properties);
      }
    },

    trackPageView(name) {
      if (this.appInsights) {
        this.appInsights.trackPageView({ name: name || document.title });
      }
    },

    trackException(exception, severityLevel) {
      if (this.appInsights) {
        this.appInsights.trackException({ exception, severityLevel });
      }
    }
  };

  window.TicketGenieTelemetry = Telemetry;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => Telemetry.init());
  } else {
    Telemetry.init();
  }
})();
