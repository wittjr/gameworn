(function($) {
    $(document).ready(function() {
        // Add "Add another" link after each inline formset
        $('.inline-group').each(function() {
            var prefix = $(this).find('.inline-related').data('prefix');
            if (!prefix) {
                prefix = $(this).find('.inline-related:first').attr('id').split('-')[0];
            }
            
            var addButton = $('<div class="add-row"><a href="#">Add another</a></div>');
            $(this).append(addButton);
            
            var totalForms = $('#id_' + prefix + '-TOTAL_FORMS');
            
            addButton.click(function(e) {
                e.preventDefault();
                var formCount = parseInt(totalForms.val());
                var row = $('.dynamic-' + prefix + ':first').clone(true);
                
                // Update form count
                totalForms.val(formCount + 1);
                
                // Update IDs and names of the new form
                row.find(':input').each(function() {
                    var name = $(this).attr('name').replace('-0-', '-' + formCount + '-');
                    var id = 'id_' + name;
                    $(this).attr({'name': name, 'id': id}).val('').removeAttr('checked');
                });
                
                // Update labels
                row.find('label').each(function() {
                    var newFor = $(this).attr('for').replace('-0-', '-' + formCount + '-');
                    $(this).attr('for', newFor);
                });
                
                // Insert new form
                row.insertBefore(addButton);
            });
        });
    });
})(django.jQuery);