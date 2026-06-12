PAGE_MAPPING = {
    # Vendor:
    '/_b_a_c_k_e_n_d/Stores/vendors/':'STR-API-VL',
    '/_b_a_c_k_e_n_d/Stores/vendors/list/' : 'STR-API-VL',
    '/_b_a_c_k_e_n_d/Stores/get_vendors/' : 'STR-API-VL',
    '/_b_a_c_k_e_n_d/Stores/vendors/update(?:/[^/]+)+/$' : 'STR-API-VL',
    '/_b_a_c_k_e_n_d/Stores/delete_vendor(?:/[^/]+)+/$' : 'STR-API-VL',

    # Items:
    '/_b_a_c_k_e_n_d/Stores/items/' : 'STR-API-IL',
    r'^/_b_a_c_k_e_n_d/Stores/items/list/?(\?.*)?$' : 'STR-API-IL',
    '/_b_a_c_k_e_n_d/Stores/items/dropdowns/' : 'STR-API-IL',
    '/_b_a_c_k_e_n_d/Stores/get_items/' : 'STR-API-IL',
    r'^/_b_a_c_k_e_n_d/Stores/update_item(?:/[^/]+)+/$' : 'STR-API-IL',
    r'^/_b_a_c_k_e_n_d/Stores/delete_item(?:/[^/]+)+/$' : 'STR-API-IL',

    # Notification:
    '/_b_a_c_k_e_n_d/Stores/inventory/check-stock/':'STR-P-ICS',

    # Travellers IN (GRN):
    '/_b_a_c_k_e_n_d/Stores/travellers-in/':'STR-API-TRL',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-in/previous-purchases/?(\?.*)?$':'STR-API-TRL',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-in/update(?:/[^/]+)+/$':'STR-API-TRL',

    # GRN Report:
    r'^/_b_a_c_k_e_n_d/Stores/travellers-in/list/?(\?.*)?$':'STR-API-TRLR',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-in/delete/?(\?.*)?$':'STR-API-TRL',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-in/update-payment-status/?(\?.*)?$':'STR-API-TRL',

    # Traveller's Intent:
    r'^/_b_a_c_k_e_n_d/Stores/travellers-intent/?(\?.*)?$':'STR-API-TIN',   
    '/_b_a_c_k_e_n_d/Stores/travellers-intent/update-item/':'STR-API-TIN',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-intent/by-date-range/?(\?.*)?$':'STR-API-TIN',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-intent/soft-delete-item/?(\?.*)?$':'STR-API-TIN',
    r'^/_b_a_c_k_e_n_d/Stores/travellers-intent/soft-delete-intent/?(\?.*)?$':'STR-API-TIN',

    # Traveller's Intent Report:
    r'^/_b_a_c_k_e_n_d/Stores/travellers-stock/?(\?.*)?$':'STR-P-TINR',

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