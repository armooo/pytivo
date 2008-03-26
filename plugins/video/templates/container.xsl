<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:template match="TiVoContainer">
        <xsl:variable name="tivos" select="Tivos"/>
        <html>
            <body>
                <h2><xsl:value-of select="Details/Title"/></h2>
                <table border="1">
                    <tr bgcolor="#9acd32">
                        <th align="left">Title</th>
                        <th align="left"></th>
                    </tr>
                        <xsl:for-each select="Item">
                            <xsl:choose>
                                <xsl:when test="Details/ContentType = 'x-container/folder'">
                                    <tr bgcolor="#bbbbbb">
                                        <td><xsl:value-of select="Details/Title"/></td>
                                        <td><a><xsl:attribute name="href"><xsl:value-of select="Links/Content/Url"/></xsl:attribute>Open Folder</a></td>
                                    </tr>   
                                </xsl:when>
                                <xsl:otherwise>
                                    <tr>
                                        <td><xsl:value-of select="Details/Title"/></td>
                                        <td><form action="/TiVoConnect">
                                            <input type="hidden" name="Command" value="Push"/>
                                            <input type="hidden" name="Container">
                                                <xsl:attribute name="value">
                                                    <xsl:value-of select="Links/Push/Container"/>
                                                </xsl:attribute>
                                            </input>
                                            <input type="hidden" name="File">
                                                <xsl:attribute name="value">
                                                    <xsl:value-of select="Links/Push/File"/>
                                                </xsl:attribute>
                                            </input>

                                            <select name="tsn">
                                                <xsl:for-each select="/TiVoContainer/Tivos/Tivo">
                                                    <option>
                                                        <xsl:attribute name="value">
                                                            <xsl:value-of select="."/>
                                                        </xsl:attribute>
                                                        <xsl:value-of select="."/>
                                                    </option>
                                                </xsl:for-each>
                                            </select>
                                            <input value="Send to TiVo" type="submit"/>
                                        </form></td>
                                    </tr>   
                                </xsl:otherwise>
                            </xsl:choose>
                        </xsl:for-each>
                </table>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>

