# -*- coding: utf-8 -*-
import copy

import itertools

from lxml.builder import E
from lxml import etree
from odoo import models, fields, api, _
from odoo.addons.base.ir.ir_ui_view import add_text_inside, add_text_before, remove_element
from odoo.tools import SKIPPED_ELEMENT_TYPES


class View(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def apply_inheritance_specs(self, source, specs_tree, inherit_id):
        """ Apply an inheriting view (a descendant of the base view)

        Apply to a source architecture all the spec nodes (i.e. nodes
        describing where and what changes to apply to some parent
        architecture) given by an inheriting view.

        :param Element source: a parent architecture to modify
        :param Elepect specs_tree: a modifying architecture in an inheriting view
        :param inherit_id: the database id of specs_arch
        :return: a modified source where the specs are applied
        :rtype: Element
        """
        # Queue of specification nodes (i.e. nodes describing where and
        # changes to apply to some parent architecture).
        specs = [specs_tree]

        while len(specs):
            spec = specs.pop(0)
            if isinstance(spec, SKIPPED_ELEMENT_TYPES):
                continue
            if spec.tag == 'data':
                specs += [c for c in spec]
                continue
            node = self.locate_node(source, spec)
            if node is not None:
                pos = spec.get('position', 'inside')
                if pos == 'replace':
                    for loc in spec.xpath(".//*[text()='$0']"):
                        loc.text = ''
                        loc.append(copy.deepcopy(node))
                    if node.getparent() is None:
                        source = copy.deepcopy(spec[0])
                    else:
                        for child in spec:
                            node.addprevious(child)
                        node.getparent().remove(node)
                elif pos == 'attributes':
                    for child in spec.getiterator('attribute'):
                        attribute = child.get('name')
                        value = child.text or ''
                        if child.get('add') or child.get('remove'):
                            assert not child.text
                            separator = child.get('separator', ',')
                            if separator == ' ':
                                separator = None  # squash spaces
                            to_add = (
                                s for s in (s.strip() for s in child.get('add', '').split(separator))
                                if s
                            )
                            to_remove = {s.strip() for s in child.get('remove', '').split(separator)}
                            values = (s.strip() for s in node.get(attribute, '').split(separator))
                            value = (separator or ' ').join(itertools.chain(
                                (v for v in values if v not in to_remove),
                                to_add
                            ))
                        if value:
                            if attribute.split(':')[0] == 'xmlns':
                                _ns, newns = attribute.split(':')
                                ns = node.nsmap
                                ns.update({newns: value})
                                etree.cleanup_namespaces(node, ns, keep_ns_prefixes=ns.keys())
                            else:
                                node.set(attribute, value)
                        elif attribute in node.attrib:
                            del node.attrib[attribute]
                elif pos == 'inside':
                    add_text_inside(node, spec.text)
                    for child in spec:
                        node.append(child)
                elif pos == 'after':
                    # add a sentinel element right after node, insert content of
                    # spec before the sentinel, then remove the sentinel element
                    sentinel = E.sentinel()
                    node.addnext(sentinel)
                    add_text_before(sentinel, spec.text)
                    for child in spec:
                        sentinel.addprevious(child)
                    remove_element(sentinel)
                elif pos == 'before':
                    add_text_before(node, spec.text)
                    for child in spec:
                        node.addprevious(child)
                else:
                    self.raise_view_error(_("Invalid position attribute: '%s'") % pos, inherit_id)

            else:
                attrs = ''.join([
                    ' %s="%s"' % (attr, spec.get(attr))
                    for attr in spec.attrib
                    if attr != 'position'
                ])
                tag = "<%s%s>" % (spec.tag, attrs)
                self.raise_view_error(_("Element '%s' cannot be located in parent view") % tag, inherit_id)

        return source