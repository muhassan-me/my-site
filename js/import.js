// Flag to ensure import runs only once per page load
let importHandled = false;

// Handle import hash from bookmarklet
function handleImportHash() {
    // Only run once per page load
    if (importHandled) return;
    importHandled = true;
    
    const hash = window.location.hash;
    if (!hash.startsWith('#import=')) return;
    
    try {
        // Extract and decode the import data
        const encoded = hash.substring(8); // Remove '#import='
        const decoded = decodeURIComponent(escape(atob(encoded)));
        const importData = JSON.parse(decoded);
        
        // Handle new bookmarklet format with text field
        if (typeof importData.text === 'string') {
            // Clear the hash BEFORE making the request
            history.replaceState(null, '', window.location.pathname);

            fetch('/api/ingest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Import': '1'
                },
                body: JSON.stringify(importData)
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { 
                        throw new Error(err.error || `Server returned ${response.status}`); 
                    });
                }
                return response.json();
            })
            .then(result => {
                if (result.ok) {
                    showSuccess(`تم التحديث: ${result.count} موقع، الإجمالي ${result.total.toLocaleString()}`);
                    initApp();
                } else {
                    showError(`خطأ في الاتصال بـ /api/ingest: ${result.error || 'Unknown error'}`);
                }
            })
            .catch(error => {
                showError(`تعذر الاتصال بـ /api/ingest: ${error.message}`);
            });
            return;
        }

        // Validate basic structure (old format: locations array)
        if (!importData || typeof importData !== 'object' || !Array.isArray(importData.locations)) {
            showError('خطأ في معالجة البيانات: Invalid import data format');
            return;
        }
        
        // Convert old format to new format
        const countries = {"Egypt": []};
        const seenNames = new Set();
        for (const loc of importData.locations) {
            if (typeof loc !== 'object' || loc === null) continue;
            const name = loc.name;
            if (!name || seenNames.has(name)) continue; // skip duplicates, keep first
            seenNames.add(name);
            countries["Egypt"].push({
                name: name,
                participants: Number(loc.participants) || 0,
                virtual: Boolean(loc.virtual),
                inPerson: Boolean(loc.inPerson),
                accepting: Boolean(loc.accepting)
            });
        }
        
        const newData = {
            capturedAt: importData.capturedAt || null,
            countries: countries
        };
        
        // Clear the hash BEFORE making the request
        history.replaceState(null, '', window.location.pathname);
        
        // Send to server using relative URL
        fetch('/api/ingest', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Import': '1'
            },
            body: JSON.stringify(newData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { 
                    throw new Error(err.error || `Server returned ${response.status}`); 
                });
            }
            return response.json();
        })
        .then(result => {
            if (result.ok) {
                // Show success message
                showSuccess(`تم التحديث: ${result.count} موقع، الإجمالي ${result.total.toLocaleString()}`);
                // Reload data and re-render
                initApp(); // This will reload everything
            } else {
                showError(`خطأ في الاتصال بـ /api/ingest: ${result.error || 'Unknown error'}`);
            }
        })
        .catch(error => {
            showError(`تعذر الاتصال بـ /api/ingest: ${error.message}`);
        });
    } catch (error) {
        showError(`خطأ في معالجة البيانات: ${error.message}`);
    }
}