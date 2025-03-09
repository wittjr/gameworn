// Dropzone.autoDiscover = false;
// console.log('test')
document.addEventListener("DOMContentLoaded", () => {
   // console.log('test')
   let element = document.getElementById("id_header_image")
   // console.log(element)
   element.addEventListener('change', (event) => {console.log('change'); console.log(element);console.log(element.value)})
   // let options = element.textContent
   // console.log(options)
   // let className = 'div.' + options.class
   // console.log(options)
   // new Dropzone(className, options)
});
