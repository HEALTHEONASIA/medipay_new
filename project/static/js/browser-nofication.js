// request permission on page load
document.addEventListener('DOMContentLoaded', function () {
  if (!Notification) {
    alert('Desktop notifications not available in your browser. Try Chromium.'); 
    return;
  }

  if (Notification.permission !== "granted")
    Notification.requestPermission();
});

function notifyMe() {
  if (Notification.permission !== "granted")
    Notification.requestPermission();
  else {
    var notification = new Notification('Notification title', {
      icon: 'http://qa.medipayasia.com/static/img/medipay_logo.png',
      body: "Hey there! You've been notified!",
    });

    notification.onclick = function () {
      window.open("http://qa.medipayasia.com");
    };

  }

}