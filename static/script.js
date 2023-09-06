


function fetchSubscribers() {
    console.log('Fetching data...');
    //check every 5 seconds and update the data
    setInterval(function () {

        fetch('/api/subscribers')
            .then(response => response.json())
            .then(data => {
                console.log('Fetched data:', data);
                Alpine.store('subscribers', data);
                console.log('Stored data:', Alpine.store('subscribers'));
            })
            .catch(error => {
                console.error('Error fetching data:', error);
            });
    }, 5000);
}