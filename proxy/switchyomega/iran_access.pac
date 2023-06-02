function FindProxyForURL(url, host, scheme) {
    "use strict";
    let patterns  = [
        /^.+\.ir$/,
        /^(.*\.)?aiocdn\.top$/,
    ];

    for (const pattern of patterns)
        if (pattern.test(host))
            return "+IRAN_ACCESS";

    return "+filter";
}
