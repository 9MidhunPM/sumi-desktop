.pragma library

function normalize(query) {
    return String(query || "").toLowerCase().trim().replace(/\s+/g, " ");
}

function score(record, now) {
    if (!record) return 0;
    return Math.max(0, record.score || 0) * Math.pow(2, -Math.max(0, now - record.lastUsed) / 2592000);
}

// Rank locally: typing never invokes a controller or writes history.
function rank(list, query, document, now) {
    const needle = normalize(query);
    const history = document && document.entries ? document.entries : {};
    return list.map(function(entry) {
        const name = normalize(entry.name);
        const detail = normalize(entry.detail);
        const record = history[entry.historyId];
        const preference = needle && record && record.queries ? score(record.queries[needle], now) : 0;
        let tier = 0;
        if (needle) {
            if (name === needle) tier = 0;
            else if (name.indexOf(needle) < 0 && detail.indexOf(needle) < 0) tier = -1;
            else if (preference > 0.01) tier = 1;
            else if (name.startsWith(needle)) tier = 2;
            else if (name.split(/[\s._()\-]+/).some(word => word.startsWith(needle))) tier = 3;
            else if (name.indexOf(needle) >= 0) tier = 4;
            else tier = 5;
        }
        return {entry: entry, tier: tier, preference: preference, usage: score(record, now), lastUsed: record ? record.lastUsed : 0};
    }).filter(item => item.tier >= 0).sort(function(a, b) {
        return a.tier - b.tier
            || (a.tier === 1 ? b.preference - a.preference : 0)
            || b.usage - a.usage
            || b.lastUsed - a.lastUsed
            || (a.entry.coldPriority || 0) - (b.entry.coldPriority || 0)
            || a.entry.name.localeCompare(b.entry.name)
            || String(a.entry.historyId || "").localeCompare(String(b.entry.historyId || ""));
    }).map(item => item.entry);
}
