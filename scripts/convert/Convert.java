import com.khubla.pdxreader.api.*;
import com.khubla.pdxreader.db.*;
import java.io.*;
import java.nio.charset.Charset;
import java.util.*;
import org.apache.commons.csv.*;

/*
 * Converts each Paradox table in the given directories to a UTF-8 CSV in the last one.
 *
 * Text is code page 437, which pdxreader assumes and the data bears out: "Fécamp" is
 * stored with 0x82. A memo field keeps its first (length - 10) bytes in the record and
 * the rest in the .MB file, which this does not read. A memo longer than the record holds
 * is therefore cut short; each table reports how many, so the loss is never silent.
 * Names.Phillimore is the only memo in the Explorer, and its references are rebuilt from
 * NameRef, which holds each one whole.
 */
public class Convert {
   static final Charset CP437 = Charset.forName("IBM437");

   public static void main(String[] args) throws Exception {
      File outDir = new File(args[args.length - 1]);
      outDir.mkdirs();
      for (int a = 0; a < args.length - 1; a++) {
         for (File f : Objects.requireNonNull(new File(args[a]).listFiles((d, n) -> n.toUpperCase().endsWith(".DB")))) {
            convert(f, new File(outDir, f.getName().replaceAll("(?i)\\.db$", ".csv")));
         }
      }
   }

   static void convert(File in, File out) throws Exception {
      int[] counts = new int[2];
      try (CSVPrinter csv = new CSVPrinter(new OutputStreamWriter(new FileOutputStream(out), "UTF-8"), CSVFormat.RFC4180)) {
         new DBTableFile().read(in, new PDXTableListener() {
            List<DBTableField> fields;
            public void start(String f) {}
            public void finish() {}
            public void header(DBTableHeader h) {
               fields = h.getFields();
               try {
                  List<String> names = new ArrayList<>();
                  for (DBTableField f : fields) names.add(f.getName().trim());
                  csv.printRecord(names);
               } catch (IOException e) { throw new UncheckedIOException(e); }
            }
            public void record(List<DBTableValue> values) {
               List<String> row = new ArrayList<>();
               for (int i = 0; i < values.size(); i++) {
                  DBTableField f = fields.get(i);
                  String v = values.get(i).getValue();
                  if (f.getFieldType() == DBTableField.FieldType.M && v != null) v = memo(f, v, counts);
                  else if (v != null && f.getFieldType() == DBTableField.FieldType.A) v = v.trim();
                  row.add(v);
               }
               counts[0]++;
               try { csv.printRecord(row); } catch (IOException e) { throw new UncheckedIOException(e); }
            }
         });
      }
      System.out.printf("%-16s %7d rows%s%n", in.getName(), counts[0], counts[1] > 0 ? "  (" + counts[1] + " memos longer than the record holds)" : "");
   }

   /* The record holds the memo's first (length - 10) bytes, then a 4-byte .MB pointer, a 4-byte little-endian total length and a 2-byte modifier. */
   static String memo(DBTableField f, String hex, int[] counts) {
      byte[] b = new byte[hex.length() / 2];
      for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
      int inline = f.getLength() - 10;
      int total = (b[inline + 4] & 0xff) | (b[inline + 5] & 0xff) << 8 | (b[inline + 6] & 0xff) << 16 | (b[inline + 7] & 0xff) << 24;
      if (total > inline) counts[1]++;
      return new String(b, 0, Math.min(total, inline), CP437).trim();
   }
}
