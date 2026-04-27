function initMultiImageDropzone(opts) {
    var dropzone    = document.getElementById(opts.dropzoneId);
    var thumbRow    = document.getElementById(opts.thumbRowId);
    var fileInput   = document.getElementById(opts.fileInputId);
    var urlInput    = document.getElementById(opts.urlInputId);
    var addUrlBtn   = document.getElementById(opts.addUrlBtnId);
    var uploadTab   = document.getElementById(opts.uploadTabId);
    var linkTab     = document.getElementById(opts.linkTabId);
    var uploadPanel = document.getElementById(opts.uploadPanelId);
    var linkPanel   = document.getElementById(opts.linkPanelId);

    if (!dropzone || !thumbRow || !fileInput) return;

    var slots     = Array.from(document.querySelectorAll('.' + opts.slotClass));
    var usedSlots = new Set();

    function activateTab(active, inactive, show, hide) {
        show.classList.remove('hidden');
        hide.classList.add('hidden');
        active.classList.add('border-blue-600', 'text-blue-600');
        inactive.classList.remove('border-blue-600', 'text-blue-600');
    }
    uploadTab.addEventListener('click', function() { activateTab(uploadTab, linkTab, uploadPanel, linkPanel); });
    linkTab.addEventListener('click',   function() { activateTab(linkTab, uploadTab, linkPanel, uploadPanel); });
    activateTab(uploadTab, linkTab, uploadPanel, linkPanel);

    function nextFreeSlot() {
        for (var i = 0; i < slots.length; i++) {
            if (!usedSlots.has(i)) return i;
        }
        return -1;
    }

    function updateDropzone() {
        dropzone.style.display = nextFreeSlot() < 0 ? 'none' : '';
    }

    function addDynamicSlot() {
        var totalInput = document.getElementById('id_' + opts.formsetPrefix + '-TOTAL_FORMS');
        if (!totalInput) return;
        var idx = parseInt(totalInput.value);
        var slotDiv = document.createElement('div');
        slotDiv.className = opts.slotClass;
        slotDiv.style.display = 'none';
        var newFile = document.createElement('input');
        newFile.type = 'file';
        newFile.name = opts.formsetPrefix + '-' + idx + '-image';
        newFile.id   = 'id_' + opts.formsetPrefix + '-' + idx + '-image';
        var newLink = document.createElement('input');
        newLink.type = 'text';
        newLink.name = opts.formsetPrefix + '-' + idx + '-link';
        newLink.id   = 'id_' + opts.formsetPrefix + '-' + idx + '-link';
        slotDiv.appendChild(newFile);
        slotDiv.appendChild(newLink);
        thumbRow.appendChild(slotDiv);
        slots.push(slotDiv);
        totalInput.value = idx + 1;
        updateDropzone();
    }

    thumbRow.querySelectorAll('.mid-saved-remove').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var card = btn.closest('.relative');
            var deleteCheckbox = card.querySelector('input[type="checkbox"]');
            if (deleteCheckbox) deleteCheckbox.checked = true;
            card.style.display = 'none';
            addDynamicSlot();
        });
    });

    function addLocalThumb(src, slotIndex) {
        usedSlots.add(slotIndex);
        var div = document.createElement('div');
        div.className = 'relative';
        div.innerHTML =
            '<div class="aspect-square rounded overflow-hidden bg-gray-100">' +
                '<img src="' + src.replace(/"/g, '&quot;') + '" alt="" class="w-full h-full object-cover">' +
            '</div>' +
            '<button type="button" class="mid-remove block mt-1 text-xs text-red-600 hover:underline">Remove</button>';
        div.querySelector('.mid-remove').addEventListener('click', function() {
            var fileEl = slots[slotIndex].querySelector('input[type="file"]');
            var linkEl = slots[slotIndex].querySelector('input[type="text"]');
            if (fileEl) fileEl.value = '';
            if (linkEl) linkEl.value = '';
            usedSlots.delete(slotIndex);
            div.remove();
            updateDropzone();
        });
        var firstSlot = thumbRow.querySelector('.' + opts.slotClass);
        thumbRow.insertBefore(div, firstSlot || null);
        updateDropzone();
    }

    function processFile(file) {
        var slot = nextFreeSlot();
        if (slot < 0 || !file) return;
        try {
            var dt = new DataTransfer();
            dt.items.add(file);
            slots[slot].querySelector('input[type="file"]').files = dt.files;
        } catch (e) {}
        var reader = new FileReader();
        reader.onload = function(e) { addLocalThumb(e.target.result, slot); };
        reader.readAsDataURL(file);
        fileInput.value = '';
    }

    function processUrl(url) {
        if (!url) return;
        var slot = nextFreeSlot();
        if (slot < 0) return;
        slots[slot].querySelector('input[type="text"]').value = url;
        addLocalThumb(url, slot);
        urlInput.value = '';
    }

    fileInput.addEventListener('change', function() {
        if (fileInput.files[0]) processFile(fileInput.files[0]);
    });
    addUrlBtn.addEventListener('click', function() { processUrl(urlInput.value.trim()); });
    urlInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); processUrl(urlInput.value.trim()); }
    });

    updateDropzone();
}
