$(document).ready(function() {
  $('#cobranzaTable').DataTable({
    order: [[1, 'desc']],
    scrollX: true,
    autoWidth: false,
    language: {
      url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/es-CL.json'
    },
    columns: [
      { width: '80px' },
      { width: '30px' },
      { width: '30px' },
      { width: '100px' },
      { width: '100px' },
      { width: '80px' },
      { width: '80px' },
      { width: '100px' },
      { width: '60px' },
      { width: '60px' },
      { width: '60px' },
      { width: '70px' },
      { width: '70px' },
      { width: '70px' },
      { width: '70px' },
      { width: '70px' }
    ]
  });
});
