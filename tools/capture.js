// Bookmarklet source
const bookmarklet = 'javascript:(function(){const text=document.body.innerText;const payload={text:text,capturedAt:new Date().toISOString()};const json=JSON.stringify(payload);const encoded=btoa(unescape(encodeURIComponent(json)));window.location="http://localhost:8080/#import="+encoded;})()';

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = bookmarklet;
}