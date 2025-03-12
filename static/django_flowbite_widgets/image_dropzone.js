document.addEventListener("DOMContentLoaded", () => {
   let element = document.getElementById("dropzone-file")
   element.addEventListener('change', (event) => {
      var fReader = new FileReader()
      fReader.readAsDataURL(element.files[0])
      fReader.onloadend = function(event){
         var pre_image = document.getElementById('dropzone-image-preview')
         if (pre_image) {
            pre_image.remove()
         }
         document.getElementById("dropzone-preview")
         var img = document.createElement('img')
         img.src = event.target.result
         img.id ='dropzone-image-preview'
         document.getElementById('dropzone-preview').appendChild(img)
          
      }
   })
})
