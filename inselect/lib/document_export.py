import shutil
import tempfile

from itertools import chain, count, izip
from pathlib import Path

import unicodecsv

from .validate_document import validate_document
from .utils import debug_print


class DocumentExport(object):
    def __init__(self, metadata_template):
        if not metadata_template:
            raise ValueError('Missing metadata_template')
        else:
            self._template = metadata_template

    def crop_fnames(self, document):
        "Generator function of instances of string"
        items = enumerate(document.items)
        fnames = (self._template.format_label(1+index, box['fields']) for index, box in items)
        suffix = self._template.cropped_file_suffix

        # Do not be tempted to use Path because fname might contain empty
        # strings if the user has done something silly, which will cause
        # Path() to raise an exception
        return (u'{0}{1}'.format(fn, suffix) for fn in fnames)

    def crops_dir(self, document):
        return document.crops_dir

    def save_crops(self, document, progress=None):
        "Saves images cropped from document.scanned to document.crops_dir"
        # TODO LH Test that cancel of export leaves existing crops dir.
        # Create temp dir alongside scan
        tempdir = tempfile.mkdtemp(dir=str(document.scanned.path.parent),
            prefix=document.scanned.path.stem + '_temp_crops')
        tempdir = Path(tempdir)
        debug_print(u'Saving crops to to temp dir [{0}]'.format(tempdir))

        crop_fnames = self.crop_fnames(document)

        try:
            # Save crops
            document.save_crops_from_image(document.scanned,
                                           (tempdir / fn for fn in crop_fnames),
                                           progress)

            # rm existing crops dir
            crops_dir = self.crops_dir(document)
            shutil.rmtree(str(crops_dir), ignore_errors=True)

            # Rename temp dir
            msg = 'Moving temp crops dir [{0}] to [{1}]'
            debug_print(msg.format(tempdir, crops_dir))
            tempdir.rename(crops_dir)
            tempdir = None

            msg = 'Saved [{0}] crops to [{1}]'
            debug_print(msg.format(document.n_items, crops_dir))

            return crops_dir
        finally:
            if tempdir:
                shutil.rmtree(str(tempdir))

    def csv_path(self, document):
        return document.document_path.with_suffix('.csv')

    def export_csv(self, document, path=None):
        """Exports metadata to a CSV file given in path, defaults to
        document.document_path with .csv extension. Path is returned.
        """
        if not path:
            path = self.csv_path(document)
        else:
            path = Path(path)

        debug_print(u'DocumentExport.export_csv to [{0}]'.format(path))

        # Field names
        fields = list(self._template.field_names())

        # Append fields that are in the document and not the template
        fields += sorted(f for f in document.metadata_fields if f not in fields)

        # Crop filenames
        crop_fnames = self.crop_fnames(document)

        # A function that returns a dict of metadata for a box
        metadata = self._template.metadata

        with path.open('wb') as f:
            w = unicodecsv.writer(f, encoding='utf8')
            w.writerow(chain(['Cropped_image_name'], fields))
            for index, fname, box in izip(count(), crop_fnames, document.items):
                md = metadata(1+index, box['fields'])
                w.writerow(chain([fname], (md.get(f) for f in fields)))

        return path

    def validation_problems(self, document):
        """Validates the document against the user template and returns any
        validation problems
        """
        validate_document(document, self._template)