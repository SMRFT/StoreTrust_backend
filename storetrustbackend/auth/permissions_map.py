PAGE_MAPPING = {
    '/_b_a_c_k_e_n_d/Stores/travellers-in/':'STR-P-TRL',
    '/_b_a_c_k_e_n_d/Stores/travellers-intent/':'STR-API-TIN',    
    '/_b_a_c_k_e_n_d/Stores/college-intent/':'STR-API-COL',
    '/_b_a_c_k_e_n_d/Stores/colleg-intent/update-item/':'STR-API-TIN',
    #r'^/_b_a_c_k_e_n_d/Stores/college-intent/by-date-range/?(\?.*)?$':'STR-API-TIN',
    #r'^/_b_a_c_k_e_n_d/Stores/college-intent/soft-delete-item/?(\?.*)?$':'STR-API-TIN',
   # r'^/_b_a_c_k_e_n_d/Stores/college-intent/soft-delete-intent/?(\?.*)?$':'STR-API-TIN',    
    '/_b_a_c_k_e_n_d/Stores/mess-intent/':'STR-API-MES', 
    '/_b_a_c_k_e_n_d/Stores/travellers-intent/update-item/':'STR-API-TIN',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-intent/by-date-range/?(\?.*)?$':'STR-API-TIN',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-intent/soft-delete-item/?(\?.*)?$':'STR-API-TIN',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-intent/soft-delete-intent/?(\?.*)?$':'STR-API-TIN',
    











}


PAGE_ACTION_MAPPING = {
    'xxx': {
        'DELETE':'RWD',
    },
}

GEN_ACTION_MAPPING = {
    'POST': 'RW',
    'PUT': 'RW',
    'DELETE': 'RW',
    'PATCH': 'RW',
    'GET': 'R',
}