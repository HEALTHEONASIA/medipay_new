/**
   * @param {string} filename The name of the file WITHOUT ending
  */
function playSound(filename) {
    document.getElementById("sound").innerHTML='<audio autoplay="autoplay"><source src="' + filename + '.mp3" type="audio/mpeg" /><source src="' + filename + '.ogg" type="audio/ogg" /><embed hidden="true" autostart="true" loop="false" src="' + filename +'.mp3" /></audio>';
}

// request permission on page load
document.addEventListener('DOMContentLoaded', function () {
  if (!Notification) {
    alert('Desktop notifications not available in your browser. Try Chromium.'); 
    return;
  }

  if (Notification.permission !== "granted")
    Notification.requestPermission();
});

function notifyMe(title, message, url) {
  if (Notification.permission !== "granted")
    Notification.requestPermission();
  else {
    var notification = new Notification(title, {
      icon: 'http://qa.medipayasia.com/static/img/medipay_logo.png',
      body: message,
    });

    notification.onclick = function () {
      window.open(url);
    };

  }

}

$.notifyDefaults({
  type: 'success',
  timer: 5000
});

var socket = io.connect('http://' + document.domain + ':' + location.port);
socket.on('connect', function() {
    socket.emit('hello', {data: 'I\'m connected!'});
    socket.on('message', function(data) {
        if (typeof preventNtfForRoom != 'undefined' && data.room_name == preventNtfForRoom) {
          // do nothing
        } else {
          $.notify({
            title: data.title,
            message: data.message,
            url: data.url,
            target: '_blank'
          });
          console.log(data);
          notifyMe(data.title, data.message, data.url);
          playSound('/static/sounds/arpeggio');
        }
    });
});

// Handling loss of internet connection
// socket.on('disconnect', function() {
//     alert('Loss of internet connection. Please reconnect with a active internet connection'); 
// });
