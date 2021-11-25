function setThisHost(host) {
	var ee = document.getElementsByClassName("thishost");
	var elist = [];
	for (var i = 0; i < ee.length; i++) {
		elist.push(ee[i])
	}
	for (var i in elist) {
		elist[i].textContent = host;
		elist[i].className = '';
	}
}

function fixThisHost() {
	var host = window.location.hostname;
	if (host != '') {
		setThisHost(host);
		document.title = host + ' - ' + document.title;
	}
}
