function FindProxyForURL(url, host, scheme) {
    "use strict";
    let patterns  = [
        /^(.*\.)?googlesyndication\.com$/, /^(.*\.)?googlevideo\.com$/, /^dl\.google\.com$/, /^account\.google\.com$/,
        /^(.*\.)?twitter\.com$/, /^(.*\.)?t\.co$/, /^(.*\.)?twimg\.com$/,
	/^(.*\.)?x\.com$/,
        /^(.*\.)?youtube\.com$/, /^(.*\.)?youtu\.be$/, /^(.*\.)?ytimg\.com$/,
        /^(.*\.)?telegram\.org$/, /^(.*\.)?t\.me$/,
        /^(.*\.)?facebook\.com$/, /^(.*\.)?fbcdn\.net$/,
        /^(.*\.)?instagram\.com$/, /^(.*\.)?cdninstagram\.com$/,
        /^(.*\.)?whatsapp\.(com|net)$/,
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
        /^(.*\.)?aiofilm\.([^\.]+)$/,
        /^(.*\.)?v2fly\.org$/,
        /^(.*\.)?overleaf\.com$/,
        /^(.*\.)?anilist\.co$/,
        /^(.*\.)?openai\.com$/,
        /^(.*\.)?statsigapi\.net$/,
        /^(.*\.)?oaistatic\.com/,
        /^(.*\.)?bbc\.com$/, /^(.*\.)?bbc\.co\.uk$/,
        /^(.*\.)?bonbast.com$/,
        /^(.*\.)?reddit.com$/, /^(.*\.)?redd.it$/,
    ];

    for (const pattern of patterns)
        if (pattern.test(host))
            return "+FILTER";

    return "+DEFAULT";
}
