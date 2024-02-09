function FindProxyForURL(url, host, scheme) {
    "use strict";
    let patterns  = [
        /^(.*\.)?googlesyndication\.com$/, /^(.*\.)?googlevideo\.com$/, /^dl\.google\.com$/, /^account\.google\.com$/,
        /^(.*\.)?twitter\.com$/, /^(.*\.)?t\.co$/, /^(.*\.)?twimg\.com$/,
        /^(.*\.)?youtube\.com$/, /^(.*\.)?ytimg\.com$/,
        /^(.*\.)?telegram\.org$/, /^(.*\.)?t\.me$/,
        /^(.*\.)?facebook\.com$/, /^(.*\.)?fbcdn\.net$/,
        /^(.*\.)?instagram\.com$/, /^(.*\.)?cdninstagram\.com$/,
        /^(.*\.)?whatsapp\.com$/,
        /^developer\.android\.com$/,
        /^(.*\.)?wordpress\.com$/, /^(.*\.)?wp\.com$/,
        /^(.*\.)?gitlab\.(com|io)$/,
        /^(.*\.)?quora\.com$/,
        /^(.*\.)?disqus\.com$/,
        /^(.*\.)?myanimelist\.net$/,
        /^(.*\.)?zoho\.(com|in|au|eu|jp)$/, /^(.*\.)?zohowebstatic\.com/, /^(.*\.)?.zohopublic\.com/, /^(.*\.)?zohocdn\.com/,
        /^1\.1\.1\.1$/,
        /^(id|hub)\.docker\.com$/,
        /^(.*\.)?jadi\.net$/,
        /^(.*\.)?autodesk\.com$/,
        /^(.*\.)?digikey\.com$/,
        /^(.*\.)?mbed\.com$/,
        /^(.*\.)?microchip\.com$/,
        /^(.*\.)?aiofilm\.(com|top|info)$/,
        /^(.*\.)?v2fly\.org$/,
        /^(.*\.)?overleaf\.com$/,
        /^(.*\.)?anilist\.co$/,
        /^(.*\.)?openai\.com$/,
	/^(.*\.)?oaistatic\.com/,
        /^(.*\.)?youtu\.be$/,
        /^(.*\.)?bbc\.com$/,
        /^(.*\.)?bbc\.co\.uk$/,
    ];

    for (const pattern of patterns)
        if (pattern.test(host))
            return "+FILTER";

    return "+DEFAULT";
}
