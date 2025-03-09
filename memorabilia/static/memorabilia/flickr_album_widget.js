function queryFlickr() {
    var albumUrl = document.getElementById('flikrAlbum').value
    var username = albumUrl.split('/')[4]
    var album = albumUrl.split('/')[6]
    var url = "{% url 'memorabilia:get_flickr_album' %}" + "?username=" + username + "&album=" + album
    fetch(url, {
        method:'GET',
        headers:{
        'Content-Type':'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        }, 
        })
        .then((response) => {
            return response.json(); //converts response to json
        })
        .then((data) => {
            console.log(data)
        //Perform actions with the response data from the view
        });
}