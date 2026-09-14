from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from html import escape

from fastapi import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SalesFunnelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_card_funnel(self, nm_id: int, date_from: str, date_to: str):
        card = await self.get_card(nm_id)
        rows = await self.get_rows(nm_id, date_from, date_to)
        chart_data = await self.get_chart_data(nm_id, date_from, date_to)
        totals = self._totals(rows)

        return {
            "card": card,
            "rows": rows,
            "chartData": chart_data,
            "totals": totals,
            "params": {"nm_id": nm_id, "date_from": date_from, "date_to": date_to},
        }

    async def get_card(self, nm_id: int):
        sql = text("""
            SELECT nmID, vendorCode, title, brand, subjectName
            FROM wbcards
            WHERE nmID = :nm_id
            LIMIT 1
        """)
        row = (await self.db.execute(sql, {"nm_id": nm_id})).mappings().first()
        return dict(row) if row else None

    async def get_rows(self, nm_id: int, date_from: str, date_to: str):
        sql = text("""
            SELECT
                h.nmId AS nm_id,
                h.date,
                h.openCount AS open_count,
                h.cartCount AS cart_count,
                h.orderCount AS order_count,
                h.orderSum AS order_sum,
                h.buyoutCount AS buyout_count,
                h.buyoutSum AS buyout_sum,
                c.title AS card_name,
                c.vendorCode AS vendor_code,
                c.brand,
                c.subjectName AS subject
            FROM wb_sales_funnel_history h
            LEFT JOIN wbcards c ON c.nmID = h.nmId
            WHERE h.nmId = :nm_id
              AND h.date BETWEEN :date_from AND :date_to
            ORDER BY h.date DESC
        """)
        params = {"nm_id": nm_id, "date_from": date_from, "date_to": date_to}
        rows = [dict(r) for r in (await self.db.execute(sql, params)).mappings().all()]

        for row in rows:
            row["open_to_cart"] = self._rate(row["cart_count"], row["open_count"])
            row["cart_to_order"] = self._rate(row["order_count"], row["cart_count"])
            row["order_to_buyout"] = self._rate(row["buyout_count"], row["order_count"])
            row["avg_order"] = self._avg(row["order_sum"], row["order_count"])

        return rows

    async def get_chart_data(self, nm_id: int, date_from: str, date_to: str):
        sql = text("""
            SELECT
                h.date,
                SUM(h.openCount) AS open_count,
                SUM(h.cartCount) AS cart_count,
                SUM(h.orderCount) AS order_count,
                SUM(h.orderSum) AS order_sum,
                SUM(h.buyoutCount) AS buyout_count,
                SUM(h.buyoutSum) AS buyout_sum
            FROM wb_sales_funnel_history h
            WHERE h.nmId = :nm_id
              AND h.date BETWEEN :date_from AND :date_to
            GROUP BY h.date
            ORDER BY h.date ASC
        """)
        params = {"nm_id": nm_id, "date_from": date_from, "date_to": date_to}
        chart_data = [dict(r) for r in (await self.db.execute(sql, params)).mappings().all()]
        return chart_data

    async def export_rows(self, nm_id: int, date_from: str, date_to: str):
        return await self.get_rows(nm_id, date_from, date_to)

    @staticmethod
    def _rate(numerator: int | None, denominator: int | None):
        numerator = float(numerator or 0)
        denominator = float(denominator or 0)
        return round(numerator / denominator * 100, 2) if denominator else None

    @staticmethod
    def _avg(total: float | None, count: int | None):
        total = float(total or 0)
        count = int(count or 0)
        return round(total / count, 2) if count else 0

    @staticmethod
    def _totals(rows):
        total_open = sum(int(r.get("open_count") or 0) for r in rows)
        total_cart = sum(int(r.get("cart_count") or 0) for r in rows)
        total_order = sum(int(r.get("order_count") or 0) for r in rows)
        total_order_sum = sum(float(r.get("order_sum") or 0) for r in rows)
        total_buyout = sum(int(r.get("buyout_count") or 0) for r in rows)
        total_buyout_sum = sum(float(r.get("buyout_sum") or 0) for r in rows)

        return {
            "open_count": total_open,
            "cart_count": total_cart,
            "order_count": total_order,
            "order_sum": round(total_order_sum, 2),
            "buyout_count": total_buyout,
            "buyout_sum": round(total_buyout_sum, 2),
            "open_to_cart": SalesFunnelService._rate(total_cart, total_open),
            "cart_to_order": SalesFunnelService._rate(total_order, total_cart),
            "order_to_buyout": SalesFunnelService._rate(total_buyout, total_order),
        }

    @staticmethod
    def build_xlsx_response(rows, nm_id: int, date_from: str, date_to: str) -> Response:
        headers = [
            "Дата",
            "Артикул WB",
            "Товар",
            "Артикул продавца",
            "Бренд",
            "Переходы",
            "Корзины",
            "CR переход→корзина, %",
            "Заказы",
            "CR корзина→заказ, %",
            "Сумма заказов, ₽",
            "Ср. заказ, ₽",
            "Выкупы",
            "SR, %",
            "Сумма выкупов, ₽",
        ]
        data = []
        for row in rows:
            data.append([
                row.get("date"),
                row.get("nm_id"),
                row.get("card_name"),
                row.get("vendor_code"),
                row.get("brand"),
                row.get("open_count"),
                row.get("cart_count"),
                row.get("open_to_cart"),
                row.get("order_count"),
                row.get("cart_to_order"),
                row.get("order_sum"),
                row.get("avg_order"),
                row.get("buyout_count"),
                row.get("order_to_buyout"),
                row.get("buyout_sum"),
            ])

        content = SalesFunnelService._make_xlsx(headers, data)
        filename = f"wb_sales_funnel_{nm_id}_{date_from}_{date_to}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @staticmethod
    def _make_xlsx(headers, data):
        ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        ET.register_namespace("", ns)
        ET.register_namespace("r", rel_ns)

        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", _content_types_xml())
            zf.writestr("_rels/.rels", _package_rels_xml())
            zf.writestr("xl/workbook.xml", _workbook_xml())
            zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml())
            zf.writestr("docProps/core.xml", _core_xml())
            zf.writestr("docProps/app.xml", _app_xml())
            zf.writestr("xl/worksheets/sheet1.xml", _worksheet_xml(headers, data))

        return output.getvalue()

    @staticmethod
    def _worksheet_xml(headers, data):
        max_col = len(headers)
        max_row = len(data) + 1
        cells = []
        cells.append(f'<dimension ref="A1:{_column_letter(max_col)}{max_row}"/>')
        cells.append('<sheetViews><sheetView workbookViewId="0"/></sheetViews>')
        cells.append('<sheetData>')

        cells.append(_row_xml(1, headers))
        for row_index, row in enumerate(data, start=2):
            cells.append(_row_xml(row_index, row))

        cells.append("</sheetData>")
        cells.append(f'<autoFilter ref="A1:{_column_letter(max_col)}{max_row}"/>')
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="%s">%s</worksheet>' % (ns, "".join(cells))

    @staticmethod
    def _row_xml(row_index, values):
        parts = [f'<row r="{row_index}">']
        for col_index, value in enumerate(values, start=1):
            ref = f"{_column_letter(col_index)}{row_index}"
            if value is None or value == "":
                parts.append(f'<c r="{ref}"/>')
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        parts.append("</row>")
        return "".join(parts)


def _content_types_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''


def _package_rels_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def _workbook_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Воронка" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''


def _workbook_rels_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''


def _core_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>wbcms</dc:creator>
  <cp:lastModifiedBy>wbcms</cp:lastModifiedBy>
</cp:coreProperties>'''


def _app_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>wbcms</Application>
</Properties>'''


def _column_letter(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result
