$results = DB::table('plates')
    ->whereRaw("serial_format REGEXP '^[A-Z]{1,2}[0-9]+[A-Z]+$'")
    ->orWhereRaw("name LIKE '%Ham%' OR name LIKE '%Radio%' OR name LIKE '%Amateur%' OR name LIKE '%CB%'")
    ->get(['id','name','serial_format','category_id']);
foreach($results as $p){
    echo $p->id . ' | ' . $p->name . ' | ' . $p->serial_format . ' | cat:' . $p->category_id . PHP_EOL;
}
