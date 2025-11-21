document.addEventListener('DOMContentLoaded', () => {
  const mainImg = document.querySelector('.turf-main-img img');
  const thumbs = document.querySelectorAll('.turf-thumbnails img');
  
  thumbs.forEach(img => {
    img.addEventListener('click', () => {
      mainImg.src = img.src;
    });
  });

  const dateInput = document.querySelector('input[name="date"]');
  if (dateInput) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.min = today;
  }
});
document.addEventListener('DOMContentLoaded', function() {
  const duration = document.getElementById('duration');
  const payable = document.getElementById('payable_now');

  // The rate will be dynamically injected from Django template
  const rateElement = document.getElementById('turf-rate');
  if (!rateElement) return;
  const rate = parseFloat(rateElement.dataset.rate);

  if (duration && payable) {
    duration.addEventListener('change', () => {
      const hours = parseInt(duration.value);
      payable.value = (rate * hours).toFixed(2);
    });
  }
});


function payNow() {
    const upi = "{{ booking.turf.owner.profile.upi_id }}";
    const name = "{{ booking.turf.owner.first_name }}";
    const amount = "{{ booking.payable_now }}";
    const booking_id = "{{ booking.id }}";

    const upiURL = `upi://pay?pa=${upi}&pn=${name}&am=${amount}&tn=Booking%20ID%20${booking_id}`;

    window.location.href = upiURL;
}
