(function patchFetchForBearerToken() {
    if (window._bearerFetchPatched) return;
    window._bearerFetchPatched = true;
    const originalFetch = window.fetch;

    function handleExpiredToken() {
        if (window._reauthInProgress) return;
        window._reauthInProgress = true;
        sessionStorage.removeItem("azureUser");
        sessionStorage.removeItem("portalUser");
        localStorage.removeItem("azureUser");
        localStorage.removeItem("portalUser");
        if (window.AzureAuth && typeof window.AzureAuth.loginWithAzure === "function") {
            console.log("🔐 Triggering Azure AD login due to 401 Unauthorized token response...");
            window.AzureAuth.loginWithAzure();
        } else {
            window.location.reload();
        }
    }

    window.fetch = async function (resource, options = {}) {
        const url = typeof resource === "string" ? resource : resource?.url || "";

        // Inject Authorization Bearer header into all backend /api/ requests
        if (url.includes("/api/") && !url.includes("/api/config")) {
            let idToken = "";
            try {
                const stored = sessionStorage.getItem("azureUser") || sessionStorage.getItem("portalUser") || localStorage.getItem("azureUser") || localStorage.getItem("portalUser");
                if (stored) {
                    const parsed = JSON.parse(stored);
                    idToken = parsed.idToken || parsed.id_token || "";
                }
            } catch (e) { }

            if (idToken) {
                const bearerHeader = `Bearer ${idToken}`;

                if (typeof resource === "object" && resource instanceof Request) {
                    if (!resource.headers.has("Authorization")) {
                        resource.headers.set("Authorization", bearerHeader);
                    }
                }

                options = options || {};
                let headers = options.headers || {};

                if (headers instanceof Headers) {
                    if (!headers.has("Authorization")) {
                        headers.set("Authorization", bearerHeader);
                    }
                } else if (Array.isArray(headers)) {
                    const hasAuth = headers.some(([k]) => k.toLowerCase() === "authorization");
                    if (!hasAuth) {
                        headers.push(["Authorization", bearerHeader]);
                    }
                } else {
                    headers = { ...headers };
                    if (!headers["Authorization"] && !headers["authorization"]) {
                        headers["Authorization"] = bearerHeader;
                    }
                }
                options.headers = headers;
            }
        }

        const response = await originalFetch.call(this, resource, options);

        // If backend responds with 401 Unauthorized for API calls (excluding config), trigger re-signin
        if (response.status === 401 && url.includes("/api/") && !url.includes("/api/config") && !url.includes("/api/users/azure-login")) {
            console.warn("⚠️ Token expired or invalid (401 response). Triggering re-authentication...");
            handleExpiredToken();
        }

        return response;
    };
})();

(function () {
    let msalInstance = null;

    /**
     * Fetch runtime config from backend to configure MSAL with Azure Client ID
     */
    async function initMsalConfig() {
        let clientId = window.AZURE_CLIENT_ID || "";
        let tenantId = window.AZURE_TENANT_ID || "";

        try {
            const res = await fetch("/api/config");
            if (res.ok) {
                const config = await res.json();
                if (config.azureClientId) clientId = config.azureClientId;
                if (config.azureTenantId) tenantId = config.azureTenantId;
            }
        } catch (e) { }

        if (clientId && (!window.msal || !window.msal.PublicClientApplication)) {
            await new Promise((resolve) => {
                const script = document.createElement("script");
                script.src = "https://alcdn.msauth.net/browser/2.38.1/js/msal-browser.min.js";
                script.onload = () => resolve();
                script.onerror = () => resolve();
                document.head.appendChild(script);
            });
        }

        if (clientId && window.msal && window.msal.PublicClientApplication && !msalInstance) {
            try {
                const msalConfig = {
                    auth: {
                        clientId: clientId,
                        authority: "https://login.microsoftonline.com/organizations",
                        redirectUri: window.location.origin,
                    },
                    cache: {
                        cacheLocation: "sessionStorage",
                        storeAuthStateInCookie: false,
                    }
                };
                msalInstance = new window.msal.PublicClientApplication(msalConfig);
            } catch (err) {
                console.warn("⚠️ [Azure Auth] MSAL initialization warning:", err.message);
            }
        }
        return clientId;
    }

    /**
     * Check if stored JWT token payload is expired
     */
    function isTokenExpired(token) {
        if (!token) return true;
        try {
            const parts = token.split(".");
            if (parts.length !== 3) return true;
            const payloadJson = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
            const payload = JSON.parse(payloadJson);
            if (payload && payload.exp) {
                // Return true if token is expired (or expires within 10 seconds buffer)
                const nowInSec = Math.floor(Date.now() / 1000);
                return payload.exp <= (nowInSec + 10);
            }
        } catch (e) {
            console.warn("⚠️ Error parsing token expiration claim:", e);
        }
        return false;
    }

    /**
     * Retrieve stored Azure User object ID and claims
     */
    /**
     * Retrieve stored Azure User object ID and claims
     */
    function getAzureUser() {
        try {
            const storedSession = sessionStorage.getItem("azureUser") || localStorage.getItem("azureUser") || sessionStorage.getItem("portalUser") || localStorage.getItem("portalUser");
            if (storedSession) {
                const parsed = JSON.parse(storedSession);
                if (parsed && (parsed.objectId || parsed.email)) {
                    if (!parsed.idToken || isTokenExpired(parsed.idToken)) {
                        console.warn("⚠️ [Auth Check] Invalid or missing Bearer token in session. Purging unauthenticated session cache.");
                        sessionStorage.removeItem("azureUser");
                        sessionStorage.removeItem("portalUser");
                        localStorage.removeItem("azureUser");
                        localStorage.removeItem("portalUser");
                        return null;
                    }
                    console.log("🔍 [Auth Check] Verified user session from cache source:", { objectId: parsed.objectId || 'N/A', email: parsed.email, role: parsed.role });
                    return parsed;
                }
            }
        } catch (e) {
            console.warn("⚠️ [Auth Check] Error reading cache:", e.message);
        }
        console.log("🔍 [Auth Check] No cached user session found in sessionStorage or localStorage.");
        return null;
    }

    /**
     * Process Azure AD Account authentication and update role & UI
     */
    async function handleAuthenticatedAccount(account, idToken, source = "MSAL Redirect / Silent", accessToken = "") {
        const objectId = account?.idTokenClaims?.oid || account?.localAccountId || account?.homeAccountId;
        const userEmail = account?.username || account?.name || "user@company.com";
        let userName = account?.name || userEmail;

        if (accessToken) {
            try {
                const graphRes = await fetch("https://graph.microsoft.com/v1.0/me", {
                    headers: { "Authorization": `Bearer ${accessToken}` }
                });
                if (graphRes.ok) {
                    const graphData = await graphRes.json();
                    if (graphData.givenName && graphData.surname) {
                        userName = `${graphData.givenName} ${graphData.surname}`.trim();
                    } else if (graphData.displayName) {
                        userName = graphData.displayName;
                    }
                    console.log("ℹ️ [Azure Auth] Retrieved real user name from Microsoft Graph API:", userName);
                }
            } catch (e) {
                console.warn("⚠️ [Azure Auth] Failed to fetch name from MS Graph API:", e.message);
            }
        }

        const rawToken = idToken || account?.idToken || account?.idTokenClaims?.rawIdToken || "";

        if (rawToken && isTokenExpired(rawToken)) {
            console.warn(`⚠️ [Auth Check] Token acquired via ${source} is expired. Purging cache.`);
            sessionStorage.removeItem("azureUser");
            sessionStorage.removeItem("portalUser");
            localStorage.removeItem("azureUser");
            localStorage.removeItem("portalUser");
            return null;
        }

        console.log(`🔑 [Auth Check] Authenticating account via ${source}. Azure Object ID:`, objectId);

        let isAdmin = false;
        let role = "Employee";
        let department = "";
        let verifiedByBackend = false;

        // Query backend for role authorization based on Object ID & verify JWT signature
        try {
            const apiRes = await fetch("/api/users/azure-login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    azure_object_id: objectId,
                    email: userEmail,
                    name: userName,
                    id_token: rawToken
                })
            });
            if (apiRes.ok) {
                const data = await apiRes.json();
                isAdmin = data.is_admin;
                role = data.role;
                department = data.department || "";
                if (data.name && data.name.trim()) {
                    userName = data.name.trim();
                }
                verifiedByBackend = true;
            } else {
                console.warn(`⚠️ [Azure Auth API] Backend rejected cached authentication (HTTP ${apiRes.status}). Purging session.`);
            }
        } catch (e) {
            console.warn("⚠️ [Azure Auth API] Backend role check error:", e.message);
        }

        if (!verifiedByBackend && rawToken) {
            sessionStorage.removeItem("azureUser");
            sessionStorage.removeItem("portalUser");
            localStorage.removeItem("azureUser");
            localStorage.removeItem("portalUser");
            return null;
        }

        if (!department) {
            department = (role && role.toLowerCase().includes("super")) ? "Upper Executive Management" : "IT Operations";
        }

        const azureUser = {
            objectId: objectId,
            email: userEmail,
            name: userName,
            role: role,
            department: department,
            isAdmin: isAdmin,
            idToken: rawToken,
            timestamp: new Date().toISOString()
        };
        sessionStorage.setItem("azureUser", JSON.stringify(azureUser));
        sessionStorage.setItem("portalUser", JSON.stringify({
            email: userEmail,
            role: role,
            name: userName,
            objectId: objectId,
            department: department,
            idToken: rawToken
        }));

        checkAdminPortalVisibility(azureUser);
        return azureUser;
    }

    /**
     * Clears stuck interaction_in_progress state from browser storage if MSAL gets locked
     */
    function clearStuckMsalInteraction() {
        try {
            [sessionStorage, localStorage].forEach(storage => {
                for (let i = storage.length - 1; i >= 0; i--) {
                    const key = storage.key(i);
                    if (key && (key.includes("msal") || key.includes("interaction"))) {
                        if (key.includes("interaction.status") || key.includes("interaction_status") || storage.getItem(key) === "interaction_in_progress") {
                            console.log(`🧹 [Azure Auth] Clearing stuck MSAL interaction key: ${key}`);
                            storage.removeItem(key);
                        }
                    }
                }
            });
        } catch (e) {
            console.warn("⚠️ [Azure Auth] Error clearing stuck interaction storage:", e);
        }
    }

    let loginInProgress = false;

    /**
     * Trigger Azure AD Login Redirect
     */
    async function loginWithAzure() {
        if (loginInProgress) {
            console.warn("⚠️ [Azure Auth] Azure AD login redirect already in progress. Skipping redundant request.");
            return null;
        }

        loginInProgress = true;
        try {
            if (autoLoginPromise) {
                try {
                    await autoLoginPromise;
                } catch (e) { }
            }

            const clientId = await initMsalConfig();

            if (msalInstance && clientId) {
                try {
                    console.log("🚀 [Auth Check] Triggering Azure AD redirect login...");
                    await msalInstance.loginRedirect({
                        scopes: ["User.Read", "openid", "profile"]
                    });
                    return;
                } catch (err) {
                    console.warn("⚠️ [Azure Auth] Azure AD redirect error:", err.message);
                    if (err.message && err.message.includes("interaction_in_progress")) {
                        console.warn("⚠️ [Azure Auth] Interaction in progress detected. Clearing stuck MSAL state and retrying...");
                        clearStuckMsalInteraction();
                        try {
                            await msalInstance.loginRedirect({
                                scopes: ["User.Read", "openid", "profile"]
                            });
                            return;
                        } catch (retryErr) {
                            console.error("❌ [Azure Auth] Retry Azure AD redirect failed:", retryErr.message);
                        }
                    }
                }
            }
            
            console.log("ℹ️ User is unauthenticated. Prompting workspace portal selection...");
            return null;
        } finally {
            loginInProgress = false;
        }
    }

    let autoLoginPromise = null;

    /**
     * Session Check on Page Load: Uses existing cached token/cookie if available ("nvm, already signed in!")
     */
    async function autoLoginAzure() {
        if (autoLoginPromise) {
            return autoLoginPromise;
        }

        autoLoginPromise = (async () => {
            const clientId = await initMsalConfig();

            // 1. Check local session storage cache first
            const storedUser = getAzureUser();
            if (storedUser) {
                console.log("🔑 [Auth Check] Using active cached session for Azure Object ID:", storedUser.objectId);
                checkAdminPortalVisibility(storedUser);
                return storedUser;
            }

            // 2. Check MSAL redirect response or active MSAL account
            if (msalInstance && clientId) {
                try {
                    const redirectResult = await msalInstance.handleRedirectPromise();
                    if (redirectResult && redirectResult.account) {
                        console.log("🔍 [Auth Check] Verified account from cache source: MSAL Redirect Result");
                        const user = await handleAuthenticatedAccount(redirectResult.account, redirectResult.idToken, "MSAL Redirect Result", redirectResult.accessToken);
                        if (user) return user;
                    }

                    const accounts = msalInstance.getAllAccounts();
                    console.log(`🔍 [Auth Check] MSAL cache account count: ${accounts.length}`);
                    if (accounts.length > 0) {
                        try {
                            const silentResult = await msalInstance.acquireTokenSilent({
                                scopes: ["User.Read", "openid", "profile"],
                                account: accounts[0]
                            });
                            if (silentResult && silentResult.account) {
                                console.log("🔍 [Auth Check] Verified account from cache source: MSAL Silent Token (Browser Cache)");
                                const user = await handleAuthenticatedAccount(silentResult.account, silentResult.idToken, "MSAL Silent Token", silentResult.accessToken);
                                if (user) return user;
                            }
                        } catch (silentErr) {
                            console.warn("⚠️ [Auth Check] MSAL Silent token acquisition failed:", silentErr.message);
                        }
                    }
                } catch (err) {
                    console.warn("⚠️ [Azure Auth] Session check notice:", err.message);
                    if (err.message && err.message.includes("interaction_in_progress")) {
                        console.warn("⚠️ [Azure Auth] Clearing stuck interaction status during session check...");
                        clearStuckMsalInteraction();
                    }
                }
            }

            console.log("🔍 [Auth Check] No valid session or MSAL account found. User is unauthenticated.");
            return null;
        })();

        return autoLoginPromise;
    }

    /**
     * Check if user is authenticated and display permitted portal options on index.html:
     * - Admin: sees Employee (NM) and Admin (AV/SS) portal buttons.
     * - Employee: sees ONLY Employee (NM) button.
     */
    function checkAdminPortalVisibility(user) {
        const azureUser = user !== undefined ? user : getAzureUser();
        const role = (azureUser?.role || "Employee").trim();
        const normalizedRole = role.toLowerCase();

        const superAdminBtn = document.getElementById("superAdminBtn");
        const employeeBtn = document.getElementById("employeeBtn");
        const adminBtn = document.getElementById("adminBtn");

        if (superAdminBtn) superAdminBtn.style.display = "none";
        if (employeeBtn) employeeBtn.style.display = "none";
        if (adminBtn) adminBtn.style.display = "none";

        const isAdmin = normalizedRole.includes("admin") || 
            normalizedRole.includes("manager") || 
            normalizedRole.includes("operations") || 
            normalizedRole.includes("super") || 
            normalizedRole.includes("lead");
        const isTicketer = normalizedRole.includes("ticketer") ||
            normalizedRole.includes("support") ||
            normalizedRole.includes("agent") ||
            isAdmin;

        if (azureUser) {
            // 1. Employee button is visible to all authenticated users
            if (employeeBtn) employeeBtn.style.display = "flex";

            // 2. Ticketer & Admin see Admin/Support portal button
            if (isTicketer) {
                if (adminBtn) adminBtn.style.display = "flex";
            }
            if (isAdmin) {
                if (superAdminBtn) superAdminBtn.style.display = "flex";
            }
        }

        const azureStatusBadge = document.getElementById("azureStatusBadge");
        if (azureStatusBadge) {
            if (azureUser) {
                azureStatusBadge.innerHTML = `<i class="ph-bold ph-shield-check" style="color:#2563eb;"></i> Active Role: <strong>${azureUser.role}</strong> &nbsp;|&nbsp; OID: <code>${azureUser.objectId}</code>`;
                azureStatusBadge.style.display = "inline-flex";
            } else {
                azureStatusBadge.innerHTML = `<i class="ph-bold ph-lock-key" style="color:#64748b;"></i> Azure AD: <span>Authenticating Session...</span>`;
                azureStatusBadge.style.display = "inline-flex";
            }
        }
    }

    /**
     * Page Route Guard: Protect sub-directories strictly based on user role:
     * - /management/*  -> Requires Admin role.
     * - /admin_AV/*     -> Requires Ticketer or Admin role.
     * - /employee_NM/* -> Allowed for Employee, Ticketer, and Admin.
     */
    function enforcePageAccessControl() {
        const path = window.location.pathname;
        const azureUser = getAzureUser();

        if (!azureUser) {
            if (path.includes("/admin_AV/") || path.includes("/management/") || path.includes("/employee_NM/")) {
                console.warn("⛔ Unauthenticated access attempt. Triggering Azure AD login...");
                if (typeof loginWithAzure === "function") {
                    loginWithAzure();
                } else {
                    window.location.href = "../index.html";
                }
                return false;
            }
            return true;
        }

        const role = (azureUser.role || "Employee").trim().toLowerCase();
        const isAdmin = role.includes("admin") || 
            role.includes("manager") || 
            role.includes("operations") || 
            role.includes("super") || 
            role.includes("lead");
        const isTicketer = role.includes("ticketer") ||
            role.includes("support") ||
            role.includes("agent") ||
            isAdmin;

        // 1. Restrict /management/ (Admin Governance Portal)
        if (path.includes("/management/")) {
            if (!isAdmin) {
                console.warn(`⛔ Access Denied: Role '${azureUser.role}' is not authorized for /management/ portal.`);
                alert(`Access Denied: Your role ('${azureUser.role}') does not have permission to access the Governance Portal.`);
                window.location.href = "../employee_NM/index.html";
                return false;
            }
        } 
        // 2. Restrict /admin_AV/ (Admin / Support Portal)
        else if (path.includes("/admin_AV/")) {
            if (!isTicketer) {
                console.warn(`⛔ Access Denied: Employee role '${azureUser.role}' cannot access /admin_AV/ portal.`);
                alert(`Access Denied: Employee accounts cannot access the Support/Admin Portal.`);
                window.location.href = "../employee_NM/index.html";
                return false;
            }
        }

        return true;
    }

    let resolveAuthReady;
    const authReady = new Promise(resolve => {
        resolveAuthReady = resolve;
    });

    window.AzureAuth = {
        getAzureUser: getAzureUser,
        loginWithAzure: loginWithAzure,
        autoLoginAzure: autoLoginAzure,
        checkAdminPortalVisibility: checkAdminPortalVisibility,
        enforcePageAccessControl: enforcePageAccessControl,
        ready: authReady
    };

    document.addEventListener("DOMContentLoaded", async function () {
        let user = null;
        try {
            user = await autoLoginAzure();
        } finally {
            resolveAuthReady(user);
        }
    });
})();
