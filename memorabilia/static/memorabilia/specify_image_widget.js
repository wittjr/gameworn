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


// $(".image-list-new").on("input", function () {
//     let $this = $(this);
//     let $clone = $this.clone();
//     let name = $clone.attr("name");
//     let n = parseInt(name.split("_")[1]) + 1;
//     name = "image_" + n;
//     $clone.val("");
//     $clone.attr("name", name);
//     $clone.appendTo($this.parent());
//     $this.removeClass("image-list-new");
//     $this.off("input", arguments.callee);
//     $clone.on("input", arguments.callee);
// });