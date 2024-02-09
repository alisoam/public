function FindProxyForURL(url, host, scheme) {
    "use strict";
    let patterns  = [
        /^(.*\.)?arvancloud\.(com|ir)$/,
        /^(.*\.)?digikala\.com$/,
        /^(.*\.)?aparat\.(com|ir)$/,
        /^(.*\.)?filimo\.(com|ir)$/,
        /^(.*\.)?cafebazaar\.(ir|org)$/,
        /^(.*\.)?zoomit\.ir$/,
        /^(.*\.)?zoomg\.ir$/,
        /^(.*\.)?adliran\.ir$/,
        /^(.*\.)?divar\.(ir|cloud|dev)$/,
    ];

    for (const pattern of patterns)
        if (pattern.test(host))
            return "+IRAN_ACCESS_WHITELIST";

    return "+iran_access";
}
