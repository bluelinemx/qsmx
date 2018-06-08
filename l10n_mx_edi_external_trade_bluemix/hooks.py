# coding: utf-8

import base64
import logging
from contextlib import closing
from os.path import join, dirname, realpath
from lxml import etree, objectify

from odoo import api, tools, SUPERUSER_ID
import requests
from odoo.modules import get_module_resource

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    _load_colony_sat_catalog(cr, registry)
    _load_customs_tax_fraction_sat_catalog(cr, registry)
    _load_mx_municipality_data(cr, registry)
    _load_mx_locality_data(cr, registry)
    _load_mx_zipcode_data(cr, registry)


def _load_colony_sat_catalog(cr, registry):
    csv_path = join(dirname(realpath(__file__)), 'data/csv', 'colony_data.csv')

    csv_file = open(csv_path, 'rb')
    cr.execute('CREATE TEMP TABLE colony_temp(country_code VARCHAR, code VARCHAR, zipcode VARCHAR, name VARCHAR, active BOOLEAN)')
    cr.copy_expert("""COPY colony_temp(country_code, code, zipcode, name, active) FROM STDIN WITH CSV HEADER DELIMITER '|'""", csv_file)
    cr.execute(
    """
    INSERT INTO res_country_colony(country_id, code, zip, name, active) 
    SELECT (SELECT id FROM res_country WHERE l10n_mx_edi_code=country_code), code, zipcode, name, true
    FROM colony_temp
    """)
    cr.execute('DROP TABLE colony_temp')


def _load_customs_tax_fraction_sat_catalog(cr, registry):
    csv_path = join(dirname(realpath(__file__)), 'data/csv', 'customs_tax_fraction_data.csv')

    csv_file = open(csv_path, 'rb')
    cr.execute('CREATE TEMP TABLE customs_tax_fraction_temp(customs_uom_code VARCHAR, code VARCHAR, name VARCHAR, availability_start_date DATE, availability_end_date DATE, import_tax DECIMAL(10,2), export_tax DECIMAL(10,2), active BOOLEAN)')
    cr.copy_expert("""COPY customs_tax_fraction_temp(customs_uom_code, code, name, availability_start_date, availability_end_date, import_tax, export_tax, active) FROM STDIN WITH CSV HEADER DELIMITER '|'""", csv_file)
    cr.execute(
    """
    INSERT INTO l10n_mx_edi_external_customs_tax_fraction(customs_uom_id, code, name, availability_start_date, availability_end_date, active) 
    SELECT (SELECT id FROM l10n_mx_edi_external_customs_uom WHERE code=customs_uom_code), code, name, availability_start_date, availability_end_date, true
    FROM customs_tax_fraction_temp
    """)
    cr.execute('DROP TABLE customs_tax_fraction_temp')


def _load_mx_municipality_data(cr, registry):
    csv_path = join(dirname(realpath(__file__)), 'data/csv', 'municipality_data.csv')

    csv_file = open(csv_path, 'rb')
    cr.execute(
        'CREATE TEMP TABLE municipality_temp(state_code VARCHAR, code VARCHAR, name VARCHAR, active BOOLEAN)')
    cr.copy_expert(
        """COPY municipality_temp(state_code, code, name, active) FROM STDIN WITH CSV HEADER DELIMITER '|'""",
        csv_file)
    cr.execute(
        """
        INSERT INTO res_country_state_municipality(country_state_id, code, name, active) 
        SELECT (SELECT res_country_state.id FROM res_country_state INNER JOIN res_country ON (res_country.id=res_country_state.country_id) WHERE res_country.code='MX' AND res_country_state.code=state_code ), code, name, true
        FROM municipality_temp
        """)
    cr.execute('DROP TABLE municipality_temp')


def _load_mx_locality_data(cr, registry):
    csv_path = join(dirname(realpath(__file__)), 'data/csv', 'locality_data.csv')

    csv_file = open(csv_path, 'rb')
    cr.execute(
        'CREATE TEMP TABLE locality_temp(state_code VARCHAR, code VARCHAR, name VARCHAR, active BOOLEAN)')
    cr.copy_expert(
        """COPY locality_temp(state_code, code, name, active) FROM STDIN WITH CSV HEADER DELIMITER '|'""",
        csv_file)
    cr.execute(
        """
        INSERT INTO res_country_state_locality(country_state_id, code, name, active) 
        SELECT (SELECT res_country_state.id FROM res_country_state INNER JOIN res_country ON (res_country.id=res_country_state.country_id) WHERE res_country.code='MX' AND res_country_state.code=state_code ), code, name, true
        FROM locality_temp
        """)
    cr.execute('DROP TABLE locality_temp')


def _load_mx_zipcode_data(cr, registry):
    csv_path = join(dirname(realpath(__file__)), 'data/csv', 'c_CodigoPostal.csv')

    csv_file = open(csv_path, 'rb')
    cr.execute(
        'CREATE TEMP TABLE zipcode_temp(zipcode VARCHAR, state_code VARCHAR, municipality_code VARCHAR, locality_code VARCHAR)')
    cr.copy_expert(
        """COPY zipcode_temp(zipcode, state_code, municipality_code, locality_code) FROM STDIN WITH CSV HEADER DELIMITER '|'""",
        csv_file)
    cr.execute(
        """
    INSERT INTO l10n_mx_edi_country_state_zipcode(country_id, country_state_id, code, municipality_id, locality_id)
        SELECT
  (SELECT res_country_state.country_id
   FROM res_country_state
     INNER JOIN res_country ON (res_country.id = res_country_state.country_id)
   WHERE res_country.code = 'MX' AND res_country_state.code = state_code),
  (SELECT res_country_state.id
   FROM res_country_state
     INNER JOIN res_country ON (res_country.id = res_country_state.country_id)
   WHERE res_country.code = 'MX' AND res_country_state.code = state_code),
  zipcode,
  (SELECT res_country_state_municipality.id
   FROM res_country_state_municipality
   INNER JOIN res_country_state ON (res_country_state.id = res_country_state_municipality.country_state_id)
   WHERE  res_country_state.code=state_code AND res_country_state_municipality.code = municipality_code),
  (SELECT res_country_state_locality.id
   FROM res_country_state_locality
   INNER JOIN res_country_state ON (res_country_state.id = res_country_state_locality.country_state_id)
   WHERE res_country_state.code=state_code AND res_country_state_locality.code = locality_code)
FROM zipcode_temp
        """)
    cr.execute('DROP TABLE zipcode_temp')


# Create xml_id, to allow make reference to this data
# cr.execute(
#     """INSERT INTO ir_model_data
#        (name, res_id, module, model)
#        SELECT concat('prod_code_sat_', code), id, 'l10n_mx_edi', 'l10n_mx_edi.product.sat.code'
#        FROM l10n_mx_edi_product_sat_code """)


# def _assign_codes_uom(cr, registry):
#     """Assign the codes in UoM of each data, this is here because the data is
#     created in the last method"""
#     tools.convert.convert_file(
#         cr, 'l10n_mx_edi', 'data/product_data.xml', None, mode='init',
#         kind='data')


