function handleLowUtilizationData(data) {
    // Display the month-end date
    const monthEndDate = new Date(data.month_end_date);
    const formattedDate = monthEndDate.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    $('.oracle-date-display').text(`Data as of: ${formattedDate} (4-week average)`);
    
    // Process below 35% utilization data
    const below35 = data.below_35;
    if (below35 && below35.length > 0) {
        let below35Html = '';
        below35.forEach(resource => {
            // Format the utilization as a percentage with 1 decimal place
            const utilization = (resource.avg_utilization * 100).toFixed(1);
            
            below35Html += `
                <tr>
                    <td>${resource.name}</td>
                    <td>${utilization}%</td>
                    <td>${resource.billing_type || 'N/A'}</td>
                    <td>${resource.rdm || 'N/A'}</td>
                </tr>
            `;
        });
        
        $('#below-35-table tbody').html(below35Html);
        $('#below-35-loading').hide();
        $('#below-35-container').show();
    } else {
        $('#below-35-loading').hide();
        $('#below-35-no-data').show();
    }
    
    // Process below 50% utilization data
    const below50 = data.below_50;
    if (below50 && below50.length > 0) {
        let below50Html = '';
        below50.forEach(resource => {
            // Format the utilization as a percentage with 1 decimal place
            const utilization = (resource.avg_utilization * 100).toFixed(1);
            
            below50Html += `
                <tr>
                    <td>${resource.name}</td>
                    <td>${utilization}%</td>
                    <td>${resource.billing_type || 'N/A'}</td>
                    <td>${resource.rdm || 'N/A'}</td>
                </tr>
            `;
        });
        
        $('#below-50-table tbody').html(below50Html);
        $('#below-50-loading').hide();
        $('#below-50-container').show();
    } else {
        $('#below-50-loading').hide();
        $('#below-50-no-data').show();
    }
} 