from __future__ import absolute_import
from os import path as opath

from blazeutils.testing import assert_equal_txt
import flask
from flask_webtest import SessionScope
import sqlalchemy.orm
from werkzeug.datastructures import MultiDict
import wrapt

from webgrid_ta.model import db

cdir = opath.dirname(__file__)

db_sess_scope = SessionScope(db)


class ModelBase(object):

    @classmethod
    def setup_class(cls):
        db_sess_scope.push()

    @classmethod
    def teardown_class(cls):
        db_sess_scope.pop()


def query_to_str(statement, bind=None):
    """
        returns a string of a sqlalchemy.orm.Query with parameters bound

        WARNING: this is dangerous and ONLY for testing, executing the results
        of this function can result in an SQL Injection attack.
    """
    if isinstance(statement, sqlalchemy.orm.Query):
        if bind is None:
            bind = statement.session.get_bind(
                statement._mapper_zero()
            )
        statement = statement.statement
    elif bind is None:
        bind = statement.bind

    if bind is None:
        raise Exception('bind param (engine or connection object) required when using with an'
                        ' unbound statement')

    dialect = bind.dialect
    compiler = statement._compiler(dialect)

    class LiteralCompiler(compiler.__class__):
        def render_literal_value(self, value, type_):
            import datetime
            """
            For date and datetime values, convert to a string
            format acceptable to the dialect. That seems to be the
            so-called ODBC canonical date format which looks
            like this:

                yyyy-mm-dd hh:mi:ss.mmm(24h)

            For other data types, call the base class implementation.
            """
            if isinstance(value, datetime.datetime):
                return "'" + value.strftime('%Y-%m-%d %H:%M:%S.%f') + "'"
            elif isinstance(value, datetime.date):
                return "'" + value.strftime('%Y-%m-%d') + "'"
            elif isinstance(value, datetime.time):
                return "'{:%H:%M:%S.%f}'".format(value)
            elif value is None:
                return 'NULL'
            else:
                return super(LiteralCompiler, self).render_literal_value(value, type_)

        def visit_bindparam(
                self, bindparam, within_columns_clause=False,
                literal_binds=False, **kwargs
        ):
            return super(LiteralCompiler, self).render_literal_bindparam(
                bindparam, within_columns_clause=within_columns_clause,
                literal_binds=literal_binds, **kwargs
            )

    compiler = LiteralCompiler(dialect, statement)
    return 'TESTING ONLY BIND: ' + compiler.process(statement)


def eq_html(html, filename):
    with open(opath.join(cdir, 'data', filename), 'rb') as fh:
        file_html = fh.read().decode('ascii')
    assert_equal_txt(html, file_html)


def assert_in_query(obj, test_for):
    if hasattr(obj, 'build_query'):
        query = obj.build_query()
    else:
        query = obj
    query_str = query_to_str(query)
    assert test_for in query_str, query_str


def assert_not_in_query(obj, test_for):
    if hasattr(obj, 'build_query'):
        query = obj.build_query()
    else:
        query = obj
    query_str = query_to_str(query)
    assert test_for not in query_str, query_str


def inrequest(*req_args, **req_kwargs):
    @wrapt.decorator
    def wrapper(wrapped, instance, args, kwargs):
        with flask.current_app.test_request_context(*req_args, **req_kwargs):
            # replaces request.args wth MultiDict so it is mutable
            flask.request.args = MultiDict(flask.request.args)
            return wrapped(*args, **kwargs)
    return wrapper
