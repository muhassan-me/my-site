// Wait for DOM to load
document.addEventListener('DOMContentLoaded', () => {
    // Check for import hash on startup
    handleImportHash();
    // Initialize the application
    initApp();
});

// Flag to ensure import runs only once per page load
let importHandled = false;

async function initApp() {
    try {
        // Load all required data
        const [latestData, pastEventsData] = await Promise.all([
            fetch('data/latest.json').then(res => {
                if (!res.ok) throw new Error(`Failed to load latest.json: ${res.status}`);
                return res.json();
            }),
            fetch('data/past_events.json').then(res => {
                if (!res.ok) throw new Error(`Failed to load past_events.json: ${res.status}`);
                return res.json();
            })
        ]);
        
        // Update last updated timestamp
        updateLastUpdated(latestData.capturedAt || new Date().toISOString());
        
        // Process and display 2026 data
        processAndDisplay2026(latestData);
        
        // Initialize past years section
        initPastYears(pastEventsData);
        
        // Draw comparison chart
        drawComparisonChart(latestData, pastEventsData);
        
    } catch (error) {
        showError(`تعذر الاتصال بـ data/latest.json أو data/past_events.json: ${error.message}`);
    }
}

function updateLastUpdated(timestamp) {
    const timestampElement = document.getElementById('timestamp');
    if (timestampElement) {
        // Format timestamp to be more readable
        const date = new Date(timestamp);
        const options = { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
        timestampElement.textContent = date.toLocaleString('ar-EG', options);
    }
}

function showError(message) {
    // Create error element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.style.backgroundColor = '#d0021b';
    errorDiv.style.color = 'white';
    errorDiv.style.padding = '1rem';
    errorDiv.style.margin = '1rem 0';
    errorDiv.style.borderRadius = '4px';
    errorDiv.textContent = message;
    
    // Insert at the top of main content
    const main = document.querySelector('main');
    if (main) {
        main.insertBefore(errorDiv, main.firstChild);
    }
    
    console.error(message);
}

function showSuccess(message) {
    // Create success element
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.style.backgroundColor = '#28a745';
    successDiv.style.color = 'white';
    successDiv.style.padding = '1rem';
    successDiv.style.margin = '1rem 0';
    successDiv.style.borderRadius = '4px';
    successDiv.textContent = message;
    
    // Insert at the top of main content
    const main = document.querySelector('main');
    // Remove any existing success/error messages first
    const existingMessages = main.querySelectorAll('.success-message, .error-message');
    existingMessages.forEach(el => el.remove());
    
    main.insertBefore(successDiv, main.firstChild);
    
    // Remove after 5 seconds
    setTimeout(() => {
        successDiv.remove();
    }, 5000);
}

// Process and display 2026 data
function processAndDisplay2026(data) {
    const locations = data.locations || [];
    
    // Calculate total participants
    const totalParticipants = locations.reduce((sum, loc) => sum + (loc.participants || 0), 0);
    
    // Find top location
    const topLocation = locations.reduce((top, loc) => 
        (loc.participants || 0) > (top.participants || 0) ? loc : top, 
        { participants: 0 }
    );
    
    // Update summary cards
    updateSummaryCards('2026', {
        totalParticipants: totalParticipants,
        locationCount: locations.length,
        topLocation: topLocation.name || 'غير معروف'
    });
    
    // Sort locations by participants descending (tie-aware ranking)
    const sortedLocations = [...locations].sort((a, b) => 
        (b.participants || 0) - (a.participants || 0)
    );
    
    // Render table with tie-aware ranking
    renderRankingTable('2026', sortedLocations, totalParticipants);
    
    // Setup search functionality
    setupSearch('2026', sortedLocations);
}

// Update summary cards for a given year
function updateSummaryCards(yearSuffix, data) {
    const summaryContainer = document.getElementById(`summary-${yearSuffix}`);
    if (!summaryContainer) return;
    
    // Clear existing content
    summaryContainer.innerHTML = '';
    
    // Total participants card
    const totalCard = createSummaryCard(
        'إجمالي المشاركين',
        data.totalParticipants.toLocaleString(),
        'users-icon'
    );
    
    // Number of locations card
    const locationsCard = createSummaryCard(
        'عدد المواقع',
        data.locationCount.toString(),
        'locations-icon'
    );
    
    // Top location card
    const topCard = createSummaryCard(
        'الأعلى',
        data.topLocation,
        'top-icon'
    );
    
    summaryContainer.appendChild(totalCard);
    summaryContainer.appendChild(locationsCard);
    summaryContainer.appendChild(topCard);
}

// Create a summary card element
function createSummaryCard(label, value, iconClass) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
        <h3>${label}</h3>
        <div class="value">${value}</div>
        <div class="label">${label}</div>
    `;
    return card;
}

// Render ranking table with tie-aware ranking
function renderRankingTable(yearSuffix, locations, totalParticipants) {
    const tbody = document.querySelector(`#ranking-table-${yearSuffix} tbody`);
    if (!tbody) return;
    
    // Clear existing rows
    tbody.innerHTML = '';
    
    if (locations.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="6">لا توجد بيانات متاحة</td>`;
        tbody.appendChild(row);
        return;
    }
    
    // Tie-aware ranking: same participants = same rank
    let currentRank = 1;
    let prevParticipants = null;
    let sameRankCount = 0;
    
    locations.forEach((loc, index) => {
        const participants = loc.participants || 0;
        
        // Check if we need to update rank
        if (prevParticipants !== null && participants !== prevParticipants) {
            currentRank += sameRankCount;
            sameRankCount = 0;
        }
        
        if (prevParticipants !== null && participants === prevParticipants) {
            sameRankCount++;
        } else {
            sameRankCount = 1; // First in this rank group
        }
        
        const rankText = sameRankCount > 1 ? `${currentRank} (م tied)` : currentRank.toString();
        
        // Calculate share of total
        const share = totalParticipants > 0 ? ((participants / totalParticipants) * 100).toFixed(1) + '%' : '0%';
        
        // Create row with BDI for RTL/LTR text isolation
        const nameCell = document.createElement('td');
        nameCell.innerHTML = `<bdi dir="ltr">${loc.name || 'غير معروف'}</bdi>`;
        
        const governorateCell = document.createElement('td');
        governorateCell.innerHTML = loc.governorate ? `<bdi dir="ltr">${loc.governorate}</bdi>` : '<span class="unmapped">غير مصنف</span>';
        
        const participantsCell = document.createElement('td');
        participantsCell.textContent = participants.toLocaleString();
        
        const shareCell = document.createElement('td');
        shareCell.textContent = share;
        
        const badgesCell = document.createElement('td');
        badgesCell.innerHTML = `
            <div class="badge-container">
                ${loc.virtual ? '<span class="badge virtual">اف</span>' : ''}
                ${loc.inPerson ? '<span class="badge inPerson">حض</span>' : ''}
                ${loc.accepting ? '<span class="badge accepting">قب</span>' : ''}
                ${loc.localLead ? '<span class="badge localLead">قائد</span>' : ''}
            </div>
        `;
        
        const rankCell = document.createElement('td');
        rankCell.textContent = rankText;
        
        // Insert cells in correct order (RTL: rank, name, governorate, participants, share, badges)
        const row = document.createElement('tr');
        row.appendChild(rankCell);
        row.appendChild(nameCell);
        row.appendChild(governorateCell);
        row.appendChild(participantsCell);
        row.appendChild(shareCell);
        row.appendChild(badgesCell);
        
        tbody.appendChild(row);
        
        prevParticipants = participants;
    });
}

// Setup search functionality for a table
function setupSearch(yearSuffix, originalLocations) {
    const searchInput = document.getElementById(`search-${yearSuffix}`);
    if (!searchInput) return;
    
    searchInput.addEventListener('input', () => {
        const searchTerm = searchInput.value.trim().toLowerCase();
        const tbody = document.querySelector(`#ranking-table-${yearSuffix} tbody`);
        if (!tbody) return;
        
        if (searchTerm === '') {
            // Show all rows
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => row.style.display = '');
            return;
        }
        
        // Filter rows based on search term
        const rows = tbody.querySelectorAll('tr');
        rows.forEach((row, index) => {
            // Skip header rows if any
            if (index === 0 && row.parentNode.tagName === 'THEAD') return;
            
            const locationName = originalLocations[index]?.name || '';
            const governorate = originalLocations[index]?.governorate || '';
            
            const matches = 
                locationName.toLowerCase().includes(searchTerm) ||
                (governorate && governorate.toLowerCase().includes(searchTerm));
                
            row.style.display = matches ? '' : 'none';
        });
    });
}

// Initialize past years section
function initPastYears(pastEventsData) {
    const yearSelect = document.getElementById('year-select');
    const pastSummary = document.getElementById('summary-past');
    const pastTbody = document.querySelector('#ranking-table-past tbody');
    const pastSearchInput = document.getElementById('search-past');
    
    if (!yearSelect || !pastSummary || !pastTbody) return;
    
    // Handle year change
    yearSelect.addEventListener('change', () => {
        const selectedYear = yearSelect.value;
        displayPastYear(selectedYear, pastEventsData);
    });
    
    // Setup search for past years
    if (pastSearchInput) {
        pastSearchInput.addEventListener('input', () => {
            const searchTerm = pastSearchInput.value.trim().toLowerCase();
            const selectedYear = yearSelect.value;
            displayPastYear(selectedYear, pastEventsData, searchTerm);
        });
    }
    
    // Display default year (2025)
    displayPastYear('2025', pastEventsData);
}

// Display data for a specific past year
function displayPastYear(year, pastEventsData, searchTerm = '') {
    const yearData = pastEventsData.years && pastEventsData.years[year];
    if (!yearData) {
        // Show error or empty state
        const pastTbody = document.querySelector('#ranking-table-past tbody');
        if (pastTbody) {
            pastTbody.innerHTML = `<tr><td colspan="4">لا توجد بيانات للسنة ${year}</td></tr>`;
        }
        return;
    }
    
    const locations = yearData.locations || [];
    const total = yearData.total || 0;
    
    // Update summary
    const pastSummary = document.getElementById('summary-past');
    if (pastSummary) {
        pastSummary.innerHTML = '';
        
        const totalCard = createSummaryCard(
            'إجمالي المشاركين',
            total.toLocaleString(),
            'users-icon'
        );
        
        const locationsCard = createSummaryCard(
            'عدد المواقع',
            locations.length.toString(),
            'locations-icon'
        );
        
        const topLocation = locations.reduce((top, loc) => 
            (loc.participants || 0) > (top.participants || 0) ? loc : top, 
            { participants: 0, name: 'غير معروف' }
        );
        
        const topCard = createSummaryCard(
            'الأعلى',
            topLocation.name || 'غير معروف',
            'top-icon'
        );
        
        pastSummary.appendChild(totalCard);
        pastSummary.appendChild(locationsCard);
        pastSummary.appendChild(topCard);
    }
    
    // Sort locations by participants descending
    const sortedLocations = [...locations].sort((a, b) => 
        (b.participants || 0) - (a.participants || 0)
    );
    
    // Filter by search term if provided
    const filteredLocations = searchTerm 
        ? sortedLocations.filter(loc => 
            (loc.name && loc.name.toLowerCase().includes(searchTerm)) ||
            (loc.governorate && loc.governorate.toLowerCase().includes(searchTerm))
          )
        : sortedLocations;
    
    // Render table
    const pastTbody = document.querySelector('#ranking-table-past tbody');
    if (pastTbody) {
        pastTbody.innerHTML = '';
        
        if (filteredLocations.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="4">لا توجد نتائج للبحث</td>`;
            pastTbody.appendChild(row);
            return;
        }
        
        // Simple ranking (no tie handling needed for past years for simplicity)
        filteredLocations.forEach((loc, index) => {
            const row = document.createElement('tr');
            
            const rankCell = document.createElement('td');
            rankCell.textContent = index + 1;
            
            const nameCell = document.createElement('td');
            nameCell.innerHTML = `<bdi dir="ltr">${loc.name || 'غير معروف'}</bdi>`;
            
            const governorateCell = document.createElement('td');
            governorateCell.innerHTML = loc.governorate ? `<bdi dir="ltr">${loc.governorate}</bdi>` : 'غير مصنف';
            
            const participantsCell = document.createElement('td');
            participantsCell.textContent = (loc.participants || 0).toLocaleString();
            
            // Insert cells in correct order (RTL: rank, name, governorate, participants)
            row.appendChild(rankCell);
            row.appendChild(nameCell);
            row.appendChild(governorateCell);
            row.appendChild(participantsCell);
            
            pastTbody.appendChild(row);
        });
    }
}

// Draw comparison chart as SVG bar chart
function drawComparisonChart(latestData, pastEventsData) {
    const chartContainer = document.getElementById('comparison-chart');
    if (!chartContainer) return;
    
    // Prepare data: 2021-2026
    const years = ['2021', '2022', '2023', '2024', '2025', '2026'];
    const totals = [];
    
    // Get totals for past years
    for (let i = 0; i < 5; i++) {
        const year = years[i];
        const yearData = pastEventsData.years && pastEventsData.years[year];
        totals.push(yearData ? yearData.total || 0 : 0);
    }
    
    // Add 2026 total
    const total2026 = latestData.locations?.reduce((sum, loc) => sum + (loc.participants || 0), 0) || 0;
    totals.push(total2026);
    
    // Find max value for scaling
    const maxValue = Math.max(...totals);
    
    // Chart dimensions
    const width = chartContainer.clientWidth || 600;
    const height = chartContainer.clientHeight || 300;
    const padding = 40;
    const barWidth = (width - 2 * padding) / years.length - 10;
    
    // Clear container
    chartContainer.innerHTML = '';
    
    // Create SVG element
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', width);
    svg.setAttribute('height', height);
    chartContainer.appendChild(svg);
    
    // Draw bars
    years.forEach((year, index) => {
        const value = totals[index];
        const barHeight = (value / maxValue) * (height - 2 * padding);
        const x = padding + index * (barWidth + 10);
        const y = height - padding - barHeight;
        
        // Bar element
        const bar = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        bar.setAttribute('x', x);
        bar.setAttribute('y', y);
        bar.setAttribute('width', barWidth);
        bar.setAttribute('height', barHeight);
        bar.setAttribute('fill', year === '2026' ? '#ffd700' : '#4a90e2');
        bar.setAttribute('rx', 4);
        bar.setAttribute('ry', 4);
        svg.appendChild(bar);
        
        // Value label on top of bar
        if (value > 0) {
            const valueText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            valueText.setAttribute('x', x + barWidth / 2);
            valueText.setAttribute('y', y - 10);
            valueText.setAttribute('text-anchor', 'middle');
            valueText.setAttribute('fill', '#e0e0e0');
            valueText.setAttribute('font-size', '12');
            valueText.textContent = value.toLocaleString();
            svg.appendChild(valueText);
        }
        
        // Year label below bar with BDI for LTR text
        const yearText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        yearText.setAttribute('x', x + barWidth / 2);
        yearText.setAttribute('y', height - padding + 20);
        yearText.setAttribute('text-anchor', 'middle');
        yearText.setAttribute('fill', '#e0e0e0');
        yearText.setAttribute('font-size', '12');
        const yearLabel = year === '2026' ? 'جاري (2026)' : year;
        yearText.innerHTML = `<bdi dir="ltr">${yearLabel}</bdi>`;
        svg.appendChild(yearText);
    });
    
    // Draw Y-axis labels (optional: percentage of max)
    for (let i = 0; i <= 5; i++) {
        const yValue = (maxValue * i) / 5;
        const yPos = height - padding - (i / 5) * (height - 2 * padding);
        
        const yText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        yText.setAttribute('x', padding - 10);
        yText.setAttribute('y', yPos + 4);
        yText.setAttribute('text-anchor', 'end');
        yText.setAttribute('fill', '#aaa');
        yText.setAttribute('font-size', '10');
        yText.textContent = yValue.toLocaleString();
        svg.appendChild(yText);
    }
}

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