document.getElementById('mobile-menu').addEventListener('click', () => {
  const nav = document.getElementById('nav-menu');
  nav.classList.toggle('active');
});

// button click feedback
document.querySelectorAll('.btn').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.style.transform = 'scale(0.95)';
    setTimeout(() => btn.style.transform = 'scale(1)', 150);
  });
});
