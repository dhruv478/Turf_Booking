new Chart(document.getElementById("bookingsChart"), {
        type: "bar",
        data: {
            labels: {{ turf_names|safe }},
            datasets: [{
                label: "Bookings",
                data: {{ turf_bookings|safe }},
                backgroundColor: "#36D1DC"
            }]
        }
    });

    new Chart(document.getElementById("turfChart"), {
        type: "doughnut",
        data: {
            labels: {{ turf_names|safe }},
            datasets: [{
                data: {{ turf_count_list|safe }},
                backgroundColor: ["#5B86E5", "#36D1DC", "#8E44AD", "#F1C40F", "#E74C3C"]
            }]
        }
    });